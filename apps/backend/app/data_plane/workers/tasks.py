"""Worker tasks for job processing and agent on-chain registration."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.chain.commerce import erc8183_client
from app.chain.sdk import erc8004_agent
from app.chain.signers import agent_signer
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.registry.agent_uri import build_agent_uri
from app.control_plane.wallets.models import Wallet
from app.core.config import SettlementMode, settings
from app.data_plane.storage.service import get_storage
from app.data_plane.workers.llm import get_llm_runner
from app.db.session import SessionLocal


def _dev_fallback_output(agent: Agent, job: Job, prompt: str) -> str:
    """Role-aware local fallback output when ``LLM_API_KEY`` is unset in development."""
    usdc_paid = f"{int(job.amount_atomic) / 1_000_000:.2f}".rstrip("0").rstrip(".")
    mode_label = (
        "ERC-8183 On-Chain Escrow"
        if job.settlement_mode == SettlementMode.ERC8183
        else "x402 EIP-3009 Gasless"
    )
    skills = {s.lower() for s in (agent.skills or [])}
    slug = (agent.slug or "").lower()

    if "solidity" in slug or "solidity-audit" in skills or "reentrancy-check" in skills:
        return (
            f"## [Báo cáo Kiểm toán Bảo mật Solidity — {agent.name}]\n\n"
            f"**Yêu cầu kiểm toán**: {prompt}\n\n"
            "### Kết quả phân tích tĩnh & luồng trạng thái\n"
            "- **[PASS] Chống Reentrancy (CEI Pattern)**: Các hàm chuyển token sử dụng "
            "`nonReentrant` và cập nhật `status` trước khi gọi `transfer`.\n"
            "- **[PASS] Chống Replay Chữ ký EIP-712 / EIP-3009**: `nonce` 32-byte và "
            "`chainId` (`43113`) được khóa chặt trong domain separator.\n"
            "- **[KHUYẾN NGHỊ]**: Kiểm tra biên `validBefore >= block.timestamp + 60` "
            "để tránh hết hạn chữ ký khi mạng cao tải.\n\n"
            f"*Quyết toán: `{usdc_paid} USDC` qua {mode_label}.*"
        )

    if "concierge" in slug or "a2a-protocol" in skills or "avalanche-docs" in skills:
        return (
            f"## [Hướng dẫn Tích hợp Hệ sinh thái Avalanche — {agent.name}]\n\n"
            f"**Câu hỏi**: {prompt}\n\n"
            "1. **Khám phá Agent Card**: Đọc `/.well-known/agent-card.json` để lấy cấu hình "
            "`x402` (`payTo`, `amount`, `asset`) và định danh `erc8004`.\n"
            "2. **Ký ủy quyền không tốn gas AVAX**: Dùng EIP-3009 `TransferWithAuthorization` "
            "ký bằng ví trình duyệt hoặc `avaxagent-sdk`.\n"
            "3. **Gửi JSON-RPC `message/send`**: Đính kèm header `X-PAYMENT` để nhận `task.id` "
            "và theo dõi kết quả qua `tasks/get`.\n\n"
            f"*Quyết toán: `{usdc_paid} USDC` qua {mode_label}.*"
        )

    return (
        f"## [Báo cáo Phân tích On-Chain — {agent.name}]\n\n"
        f"**Yêu cầu của bạn**: {prompt}\n\n"
        "- **Thanh khoản Avalanche C-Chain**: Dòng vốn USDC/AVAX trên Trader Joe Liquidity Book "
        "và Aave v3 duy trì độ sâu ổn định.\n"
        "- **Lợi suất tham chiếu**: APY USDC ~4.8% (Aave v3), sAVAX ~5.2% (Benqi).\n"
        "- **Đánh giá rủi ro**: Ưu tiên sử dụng Circle USDC chuẩn EIP-3009 nguyên bản.\n\n"
        f"*Quyết toán: `{usdc_paid} USDC` qua {mode_label}.*"
    )


def _extract_prompt(request: dict[str, Any]) -> str:
    msg = request.get("message") or request.get("prompt") or ""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, list):
        parts: list[str] = []
        for item in msg:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(_extract_prompt(item))
        return "\n".join(parts)
    if isinstance(msg, dict):
        if "text" in msg:
            return str(msg["text"])
        if "parts" in msg:
            # A2A ``Message``: ``{"role": "user", "parts": [{"kind": "text", "text": ...}]}``.
            return _extract_prompt({"message": msg["parts"]})
        if "content" in msg:
            content = msg["content"]
            return (
                _extract_prompt(content)
                if isinstance(content, dict)
                else _extract_prompt({"message": content})
            )
    return str(msg)


async def run_job(ctx: dict[str, Any], job_id: str) -> None:
    """Execute LLM workflow for a funded job and store deliverable."""
    session: AsyncSession | None = ctx.get("session")
    if session is not None:
        await _run_job_with_session(session, job_id)
    else:
        async with SessionLocal() as db:
            await _run_job_with_session(db, job_id)
            await db.commit()


async def _run_job_with_session(db: AsyncSession, job_id: str) -> None:
    job_uuid = uuid.UUID(job_id)
    job = (await db.execute(select(Job).where(Job.id == job_uuid))).scalar_one_or_none()
    if not job or job.status != JobStatus.FUNDED:
        return

    agent = (await db.execute(select(Agent).where(Agent.id == job.agent_id))).scalar_one_or_none()
    if not agent:
        job.status = JobStatus.FAILED
        job.error = "Agent not found"
        await add_event(db, job, "failed", message="Agent not found")
        await db.flush()
        return

    job.status = JobStatus.RUNNING
    await add_event(db, job, "llm_started")
    # Commit now: the LLM call can take a while and the job log polls from
    # another session, which would otherwise see "funded" until the end.
    await db.commit()

    try:
        prompt = _extract_prompt(job.request)
        llm_cfg = agent.llm_config or {}
        provider = llm_cfg.get("provider", settings.llm_provider)
        model = llm_cfg.get("model", settings.llm_model)
        system = llm_cfg.get("system_prompt") or llm_cfg.get("system", "")
        temperature = float(llm_cfg.get("temperature", 0.7))

        try:
            llm = get_llm_runner(provider=provider)
        except Exception:
            if settings.environment == "development":
                class _DevMockLlm:
                    async def complete(self, **kwargs: Any) -> str:
                        return _dev_fallback_output(agent, job, prompt)

                llm = _DevMockLlm()
            else:
                raise
        output = await llm.complete(
            model=model,
            system=system,
            prompt=prompt,
            temperature=temperature,
        )

        storage = get_storage()
        deliverable_data = {
            "job_id": str(job.id),
            "agent": agent.slug,
            "output": output,
        }
        deliverable_uri = await storage.upload(deliverable_data, filename=f"job-{job.id}")
        canonical = json.dumps(deliverable_data, sort_keys=True, separators=(",", ":"))
        keccak_bytes = Web3.keccak(text=canonical)
        deliverable_hash = "0x" + keccak_bytes.hex().removeprefix("0x")

        job.deliverable_uri = deliverable_uri
        job.deliverable_hash = deliverable_hash

        if job.settlement_mode == SettlementMode.ERC8183:
            if job.chain_job_id is None:
                raise RuntimeError("ERC-8183 job missing chain_job_id")
            wallet = (
                await db.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
            ).scalar_one_or_none()
            if not wallet:
                raise RuntimeError("Agent wallet not found")
            signer = agent_signer(wallet)
            commerce_client = erc8183_client(signer)
            submit_tx = await asyncio.to_thread(
                commerce_client.submit_result,
                int(job.chain_job_id),
                deliverable_uri,
                bytes(keccak_bytes),
            )
            job.submit_tx_hash = submit_tx
            job.status = JobStatus.SUBMITTED
            await add_event(db, job, "submitted", uri=deliverable_uri, tx_hash=submit_tx)
        else:
            job.status = JobStatus.SUBMITTED
            await add_event(db, job, "submitted", uri=deliverable_uri)
            if job.settlement_mode == SettlementMode.X402:
                job.status = JobStatus.SETTLED
                await add_event(db, job, "settled")

        await db.flush()
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:2000]
        await add_event(db, job, "failed", message=str(exc))
        await db.flush()


async def refresh_agent_uri(ctx: dict[str, Any], agent_id: str) -> None:
    session: AsyncSession | None = ctx.get("session")
    if session is not None:
        await _refresh_agent_uri_with_session(session, agent_id)
    else:
        async with SessionLocal() as db:
            await _refresh_agent_uri_with_session(db, agent_id)
            await db.commit()


async def _refresh_agent_uri_with_session(db: AsyncSession, agent_id: str) -> None:
    agent_uuid = uuid.UUID(agent_id)
    agent = (await db.execute(select(Agent).where(Agent.id == agent_uuid))).scalar_one_or_none()
    if not agent or agent.erc8004_agent_id is None:
        return

    wallet = (
        await db.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
    ).scalar_one_or_none()
    if not wallet:
        raise RuntimeError("Agent wallet not found")

    signer = agent_signer(wallet)
    client = erc8004_agent(signer)
    new_uri = await asyncio.to_thread(build_agent_uri, agent)

    res = await asyncio.to_thread(client.set_agent_uri, int(agent.erc8004_agent_id), new_uri)
    if not res or not res.get("success"):
        err_msg = res.get("error", "Updating agent URI on-chain failed") if res else "Failed"
        raise RuntimeError(err_msg)

    agent.agent_uri = new_uri
    await db.flush()


async def register_agent(ctx: dict[str, Any], agent_id: str) -> None:
    session: AsyncSession | None = ctx.get("session")
    if session is not None:
        await _register_agent_with_session(session, agent_id)
    else:
        async with SessionLocal() as db:
            try:
                await _register_agent_with_session(db, agent_id)
            finally:
                # Commit on failure too, so the FAILED status is visible and retryable.
                await db.commit()


async def _register_agent_with_session(db: AsyncSession, agent_id: str) -> None:
    agent_uuid = uuid.UUID(agent_id)
    agent = (await db.execute(select(Agent).where(Agent.id == agent_uuid))).scalar_one_or_none()
    if not agent:
        return

    if agent.erc8004_agent_id is not None:
        return

    wallet = (
        await db.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
    ).scalar_one_or_none()
    if not wallet:
        agent.status = AgentStatus.PROVISIONING
        await db.flush()
        raise RuntimeError("Agent wallet not found")

    signer = agent_signer(wallet)
    client = erc8004_agent(signer)
    agent_uri = await asyncio.to_thread(build_agent_uri, agent)

    try:
        res = await asyncio.to_thread(client.register_agent, agent_uri)
        if not res or not res.get("success"):
            err_msg = res.get("error", "Registration on-chain failed") if res else "Failed"
            raise RuntimeError(err_msg)

        agent.erc8004_agent_id = res.get("agentId")
        agent.registration_tx_hash = res.get("transactionHash")
        agent.agent_uri = agent_uri
        agent.status = AgentStatus.ACTIVE
        await db.flush()
    except Exception as e:
        agent.status = AgentStatus.FAILED
        await db.flush()
        raise e

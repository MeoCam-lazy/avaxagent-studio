"""Worker tasks for job processing and agent on-chain registration."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

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
    await db.flush()

    try:
        prompt = _extract_prompt(job.request)
        llm_cfg = agent.llm_config or {}
        model = llm_cfg.get("model", settings.llm_model)
        system = llm_cfg.get("system_prompt") or llm_cfg.get("system", "")
        temperature = float(llm_cfg.get("temperature", 0.7))

        llm = get_llm_runner()
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
            await _register_agent_with_session(db, agent_id)
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
        agent.status = AgentStatus.PROVISIONING
        await db.flush()
        raise e

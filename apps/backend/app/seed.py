"""Demo seed script for 3 reference agents on Avalanche C-Chain.

Run from ``apps/backend``::

    uv run python -m app.seed
    uv run python -m app.seed --owner 0xYourWalletAddress
    uv run python -m app.seed --agents-only
    uv run python -m app.seed --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.chain import network as net
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.agents.schemas import AgentCreate, LLMConfig
from app.control_plane.agents.service import AgentService
from app.control_plane.billing.ledger import record_income
from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.registry.agent_uri import build_agent_uri
from app.control_plane.registry.schemas import RegistrationRequest
from app.control_plane.registry.service import RegistryService
from app.control_plane.wallets.models import Wallet
from app.control_plane.wallets.schemas import WalletPolicy
from app.control_plane.wallets.service import WalletService
from app.core.config import SettlementMode, settings
from app.data_plane.storage.service import get_storage
from app.db.base import Base
from app.db.session import SessionLocal, engine

log = logging.getLogger(__name__)

DEFAULT_DEMO_OWNER = "0x000000000000000000000000000000000000dEaD"
DEMO_CLIENT_ADDRESS = "0x000000000000000000000000000000000000cafe"


@dataclass(frozen=True)
class ReferenceAgentSpec:
    slug: str
    name: str
    description: str
    skills: list[str]
    system_prompt: str
    temperature: float
    price_atomic: int
    erc8004_agent_id: int
    demo_wallet_address: str
    demo_prompt: str
    demo_output: str


REFERENCE_AGENTS: tuple[ReferenceAgentSpec, ...] = (
    ReferenceAgentSpec(
        slug="avax-defi-analyst",
        name="AVAX DeFi Analyst",
        description=(
            "Phân tích dữ liệu on-chain trên Avalanche C-Chain và các L1s: thanh khoản "
            "Trader Joe, lãi suất Benqi/Aave v3, dòng tiền USDC/EURC và chỉ số rủi ro DeFi."
        ),
        skills=["defi-analytics", "avalanche-c-chain", "yield-research", "tokenomics"],
        system_prompt=(
            "You are AVAX DeFi Analyst, an on-chain financial research agent operating on "
            "Avalanche C-Chain (43114) and Fuji (43113). Provide structured, data-driven "
            "breakdowns of liquidity pools, lending yields, USDC/EURC settlement flows, "
            "and protocol risk metrics."
        ),
        temperature=0.2,
        price_atomic=250_000,  # 0.25 USDC
        erc8004_agent_id=101,
        demo_wallet_address="0x1000000000000000000000000000000000000101",
        demo_prompt="Summarize USDC liquidity and yield opportunities on Avalanche C-Chain.",
        demo_output=(
            "## Avalanche C-Chain USDC Yield & Liquidity Report\n\n"
            "1. **Aave v3 (Avalanche)**: Supply APY ~4.8% on native USDC with deep utilization.\n"
            "2. **Benqi Lending**: Stable borrow demand with AVAX liquid-staking collateral.\n"
            "3. **Trader Joe Liquidity Book**: Tight 1-bps bins on AVAX/USDC and EURC/USDC.\n"
            "4. **Risk Note**: Prefer native Circle USDC (EIP-3009 enabled) for x402 settlement."
        ),
    ),
    ReferenceAgentSpec(
        slug="solidity-security-auditor",
        name="Solidity Security Auditor",
        description=(
            "Kiểm toán hợp đồng thông minh Solidity trên Avalanche: rà soát lỗ hổng reentrancy, "
            "kiểm tra phân quyền, EIP-3009 TransferWithAuthorization, ERC-8004 và ERC-8183 escrow."
        ),
        skills=["solidity-audit", "erc-8004", "erc-8183", "reentrancy-check"],
        system_prompt=(
            "You are Solidity Security Auditor, a smart-contract security specialist for "
            "Avalanche EVM contracts. Audit Solidity code for reentrancy, access-control flaws, "
            "signature replay (EIP-712 / EIP-3009), and ERC-8183 escrow state transitions."
        ),
        temperature=0.1,
        price_atomic=500_000,  # 0.50 USDC
        erc8004_agent_id=102,
        demo_wallet_address="0x1000000000000000000000000000000000000102",
        demo_prompt="Audit an EIP-3009 payment receiver and ERC-8183 escrow settlement flow.",
        demo_output=(
            "## Security Audit Summary\n\n"
            "- **[PASS] EIP-3009 Nonce Uniqueness**: `payment_nonce` is indexed unique, "
            "preventing replay across x402 calls.\n"
            "- **[PASS] ERC-8183 Optimistic Dispute Window**: `OptimisticPolicy` enforces "
            "the dispute window before `router.settle(jobId)` can release funds.\n"
            "- **[RECOMMENDATION]**: Verify `validBefore` margin >= 60s before relay broadcast."
        ),
    ),
    ReferenceAgentSpec(
        slug="avalanche-ecosystem-concierge",
        name="Avalanche Ecosystem Concierge",
        description=(
            "Trợ lý đa ngôn ngữ (Việt / Anh) hướng dẫn tích hợp A2A protocol, thanh toán vi mô "
            "x402 bằng USDC trên Avalanche Fuji/Mainnet và đăng ký danh tính agent ERC-8004."
        ),
        skills=["translation", "summarization", "a2a-protocol", "avalanche-docs"],
        system_prompt=(
            "You are Avalanche Ecosystem Concierge, a bilingual (Vietnamese & English) "
            "developer assistant for Avaxagent Studio. Help users integrate A2A endpoints, "
            "sign x402 EIP-3009 authorizations, and register ERC-8004 agent identities."
        ),
        temperature=0.3,
        price_atomic=100_000,  # 0.10 USDC
        erc8004_agent_id=103,
        demo_wallet_address="0x1000000000000000000000000000000000000103",
        demo_prompt="Hướng dẫn gọi agent qua A2A gateway và thanh toán x402 trên Avalanche Fuji.",
        demo_output=(
            "## Hướng dẫn gọi Agent qua A2A + x402 trên Avalanche Fuji\n\n"
            "1. Gửi `POST /agents/{slug}/a2a` để nhận phản hồi `HTTP 402` kèm thông tin `accepts`.\n"
            "2. Ký ủy quyền `TransferWithAuthorization` (EIP-3009) cho USDC trên chain `43113`.\n"
            "3. Gửi lại request kèm header `X-PAYMENT` — Gateway sẽ quyết toán on-chain và trả "
            "về `task.id` để theo dõi kết quả."
        ),
    ),
)


@dataclass(frozen=True)
class SeedSummary:
    agents: list[Agent]
    jobs_created: int


async def ensure_tables() -> None:
    """Create database tables if migrations have not been run yet."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_reference_agents(
    db: AsyncSession,
    *,
    owner_id: str = DEFAULT_DEMO_OWNER,
    include_demo_activity: bool = True,
    provision_live: bool = False,
) -> SeedSummary:
    """Idempotently seed the 3 reference agents (and optional demo jobs/ledger)."""
    normalized_owner = owner_id.lower()
    cid = net.chain_id()
    asset_addr = net.payment_asset_address()
    seeded_agents: list[Agent] = []
    jobs_created = 0

    for idx, spec in enumerate(REFERENCE_AGENTS, start=1):
        existing = (
            await db.execute(select(Agent).where(Agent.slug == spec.slug))
        ).scalar_one_or_none()

        if existing is None and provision_live:
            created = await AgentService(db).create(
                normalized_owner,
                AgentCreate(
                    slug=spec.slug,
                    name=spec.name,
                    description=spec.description,
                    llm_config=LLMConfig(
                        provider=settings.llm_provider,
                        model=settings.llm_model,
                        system_prompt=spec.system_prompt,
                        temperature=spec.temperature,
                    ),
                    skills=list(spec.skills),
                    settlement_mode=SettlementMode.X402,
                    price_atomic=spec.price_atomic,
                    is_public=True,
                ),
            )
            await WalletService(db).provision(normalized_owner, created.id)
            await RegistryService(db).register(
                normalized_owner, created.id, RegistrationRequest()
            )
            agent = (
                await db.execute(select(Agent).where(Agent.id == created.id))
            ).scalar_one()
            seeded_agents.append(agent)
            continue

        wallet = await _ensure_demo_wallet(db, spec, cid)

        if existing is None:
            agent = Agent(
                owner_id=normalized_owner,
                slug=spec.slug,
                name=spec.name,
                description=spec.description,
                status=AgentStatus.ACTIVE,
                is_public=True,
                llm_config={
                    "provider": settings.llm_provider,
                    "model": settings.llm_model,
                    "system_prompt": spec.system_prompt,
                    "temperature": spec.temperature,
                },
                skills=list(spec.skills),
                settlement_mode=SettlementMode.X402,
                price_atomic=spec.price_atomic,
                chain_id=cid,
                erc8004_agent_id=spec.erc8004_agent_id,
                registration_tx_hash=f"0x{idx:02x}" + "11" * 31,
                wallet_id=wallet.id,
            )
            db.add(agent)
            await db.flush()
        else:
            agent = existing
            agent.owner_id = normalized_owner
            agent.name = spec.name
            agent.description = spec.description
            agent.status = AgentStatus.ACTIVE
            agent.is_public = True
            agent.llm_config = {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "system_prompt": spec.system_prompt,
                "temperature": spec.temperature,
            }
            agent.skills = list(spec.skills)
            agent.settlement_mode = SettlementMode.X402
            agent.price_atomic = spec.price_atomic
            agent.chain_id = cid
            if agent.erc8004_agent_id is None:
                agent.erc8004_agent_id = spec.erc8004_agent_id
            if agent.registration_tx_hash is None:
                agent.registration_tx_hash = f"0x{idx:02x}" + "11" * 31
            if agent.wallet_id is None:
                agent.wallet_id = wallet.id
            agent.deleted_at = None
            await db.flush()

        agent.agent_uri = build_agent_uri(agent)
        await db.flush()

        if include_demo_activity:
            created_now = await _ensure_demo_job_and_ledger(
                db, agent=agent, spec=spec, idx=idx, chain_id=cid, asset=asset_addr
            )
            if created_now:
                jobs_created += 1

        seeded_agents.append(agent)

    await db.commit()
    for a in seeded_agents:
        await db.refresh(a)

    return SeedSummary(agents=seeded_agents, jobs_created=jobs_created)


async def _ensure_demo_wallet(
    db: AsyncSession, spec: ReferenceAgentSpec, chain_id: int
) -> Wallet:
    checksum_addr = Web3.to_checksum_address(spec.demo_wallet_address)
    wallet = (
        await db.execute(select(Wallet).where(Wallet.address == checksum_addr))
    ).scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(
            provider="turnkey",
            turnkey_sub_org_id=f"demo-sub-org-{spec.slug}",
            turnkey_wallet_id=f"demo-wallet-{spec.slug}",
            address=checksum_addr,
            chain_id=chain_id,
            policy=WalletPolicy().model_dump(),
        )
        db.add(wallet)
        await db.flush()
    return wallet


async def _ensure_demo_job_and_ledger(
    db: AsyncSession,
    *,
    agent: Agent,
    spec: ReferenceAgentSpec,
    idx: int,
    chain_id: int,
    asset: str,
) -> bool:
    nonce = f"0x{idx:02x}" + "aa" * 31
    existing_job = (
        await db.execute(select(Job).where(Job.payment_nonce == nonce))
    ).scalar_one_or_none()
    if existing_job is not None:
        return False

    payment_tx = f"0x{idx:02x}" + "bb" * 31
    job = Job(
        agent_id=agent.id,
        settlement_mode=SettlementMode.X402,
        status=JobStatus.SETTLED,
        chain_id=chain_id,
        client_address=Web3.to_checksum_address(DEMO_CLIENT_ADDRESS),
        amount_atomic=spec.price_atomic,
        asset=asset,
        payment_nonce=nonce,
        request={"message": spec.demo_prompt},
        payment_tx_hash=payment_tx,
        settle_tx_hash=payment_tx,
    )
    db.add(job)
    await db.flush()

    deliverable_payload: dict[str, Any] = {
        "job_id": str(job.id),
        "agent": agent.slug,
        "output": spec.demo_output,
    }
    try:
        storage = get_storage()
        deliverable_uri = await storage.upload(deliverable_payload, filename=f"job-{job.id}")
    except Exception:
        deliverable_uri = f"file://.agent-data/job-{job.id}.json"

    canonical = json.dumps(deliverable_payload, sort_keys=True, separators=(",", ":"))
    deliverable_hash = "0x" + Web3.keccak(text=canonical).hex().removeprefix("0x")
    job.deliverable_uri = deliverable_uri
    job.deliverable_hash = deliverable_hash
    await db.flush()

    await add_event(db, job, "funded", tx_hash=payment_tx)
    await add_event(db, job, "llm_started")
    await add_event(db, job, "submitted", uri=deliverable_uri)
    await add_event(db, job, "settled", tx_hash=payment_tx)

    await record_income(
        db,
        amount=spec.price_atomic,
        asset=asset,
        job=job,
        tx_hash=payment_tx,
        log_index=0,
    )
    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed 3 reference agents and demo activity for Avaxagent Studio."
    )
    parser.add_argument(
        "--owner",
        default=DEFAULT_DEMO_OWNER,
        help=f"Owner wallet address (default: {DEFAULT_DEMO_OWNER})",
    )
    parser.add_argument(
        "--agents-only",
        action="store_true",
        help="Seed only the 3 reference agents and wallets without sample jobs/ledger rows.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Provision real Turnkey sub-org wallets and enqueue ERC-8004 registration.",
    )
    return parser.parse_args(argv)


async def _run_cli(args: argparse.Namespace) -> SeedSummary:
    await ensure_tables()
    async with SessionLocal() as db:
        result = await seed_reference_agents(
            db,
            owner_id=args.owner,
            include_demo_activity=not args.agents_only,
            provision_live=args.live,
        )
    for agent in result.agents:
        log.info(
            "Seeded agent %-30s | price=%s USDC | status=%s | erc8004=#%s",
            agent.slug,
            agent.price_atomic / 1_000_000,
            agent.status.value,
            agent.erc8004_agent_id,
        )
    log.info(
        "Done: %d reference agents ready (%d demo jobs created).",
        len(result.agents),
        result.jobs_created,
    )
    return result


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _parse_args(argv)
    asyncio.run(_run_cli(args))


if __name__ == "__main__":
    main()

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.wallets.models import Wallet
from app.core.config import SettlementMode


async def make_agent(
    db: AsyncSession,
    owner_id: str = "dev-user",
    **kw: Any,
) -> Agent:
    slug = kw.pop("slug", f"agent-{uuid.uuid4().hex[:8]}")
    name = kw.pop("name", "Test Agent")
    agent = Agent(
        owner_id=owner_id,
        slug=slug,
        name=name,
        status=kw.pop("status", AgentStatus.DRAFT),
        settlement_mode=kw.pop("settlement_mode", SettlementMode.X402),
        chain_id=kw.pop("chain_id", 43113),
        price_atomic=kw.pop("price_atomic", 1_000_000),
        **kw,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def make_wallet(
    db: AsyncSession,
    **kw: Any,
) -> Wallet:
    addr = kw.pop("address", f"0x{uuid.uuid4().hex.rjust(40, '0')[:40]}")
    wallet = Wallet(
        provider=kw.pop("provider", "turnkey"),
        address=addr,
        chain_id=kw.pop("chain_id", 43113),
        policy=kw.pop("policy", {}),
        **kw,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return wallet


async def make_job(
    db: AsyncSession,
    agent: Agent,
    **kw: Any,
) -> Job:
    job = Job(
        agent_id=agent.id,
        settlement_mode=kw.pop("settlement_mode", agent.settlement_mode),
        status=kw.pop("status", JobStatus.FUNDED),
        chain_id=kw.pop("chain_id", agent.chain_id),
        asset=kw.pop("asset", "0x5425890298aed601595a70AB815c96711a31Bc65"),
        amount_atomic=kw.pop("amount_atomic", agent.price_atomic),
        **kw,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

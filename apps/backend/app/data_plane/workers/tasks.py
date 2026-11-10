"""Worker tasks for job processing and agent on-chain registration."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain.sdk import erc8004_agent
from app.chain.signers import agent_signer
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.registry.agent_uri import build_agent_uri
from app.control_plane.wallets.models import Wallet
from app.core.errors import NotImplementedYet
from app.db.session import SessionLocal


async def run_job(ctx: dict[str, Any], job_id: str) -> None:
    raise NotImplementedYet("workers.run_job")


async def register_agent(ctx: dict[str, Any], agent_id: str) -> None:
    session: AsyncSession | None = ctx.get("session")
    if session is not None:
        await _register_agent_with_session(session, agent_id)
    else:
        async with SessionLocal() as db:
            await _register_agent_with_session(db, agent_id)


async def _register_agent_with_session(db: AsyncSession, agent_id: str) -> None:
    agent_uuid = uuid.UUID(agent_id)
    agent = (
        await db.execute(select(Agent).where(Agent.id == agent_uuid))
    ).scalar_one_or_none()
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
    agent_uri = build_agent_uri(agent)

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

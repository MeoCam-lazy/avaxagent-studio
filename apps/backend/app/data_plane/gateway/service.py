"""Gateway logic.

* ``agent_card``: build the A2A agent card from the agent config (name,
  skills, ``url = {PUBLIC_GATEWAY_URL}/agents/{slug}/a2a``) and advertise the
  ERC-8004 identity (``eip155:{chain_id}:{registry}`` + agentId).
* ``handle_a2a``:
    - ``negotiate``: quote price / terms from the agent config.
    - x402 mode: without ``X-PAYMENT`` answer 402 with ``X402Accept``
      (Avalanche USDC, EIP-3009); with it, verify + settle through a
      facilitator, create a FUNDED ``Job`` and enqueue ``RUN_JOB``.
    - erc8183 mode: return the commerce job params; the indexer picks up
      ``JobFunded`` (requires the studio-deployed contracts).
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain import network as net
from app.control_plane.agents.models import AgentStatus
from app.control_plane.agents.service import AgentService
from app.control_plane.wallets.models import Wallet
from app.core.config import settings
from app.core.errors import NotImplementedYet
from app.data_plane.gateway.schemas import JsonRpcRequest


async def agent_card(db: AsyncSession, slug: str) -> dict[str, Any]:
    agent = await AgentService(db).get_by_slug(slug)
    if not agent or agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "agent_not_found"},
        )

    wallet_address: str | None = None
    if agent.wallet_id:
        wallet = (
            await db.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
        ).scalar_one_or_none()
        if wallet:
            wallet_address = wallet.address

    skills: list[dict[str, Any]] = []
    for s in agent.skills or []:
        if isinstance(s, dict):
            skills.append(s)
        elif isinstance(s, str):
            skills.append({"id": s, "name": s})

    return {
        "name": agent.name,
        "description": agent.description,
        "url": f"{settings.public_gateway_url}/agents/{slug}/a2a",
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": skills,
        "extensions": {
            "x402": {
                "network": net.caip2(),
                "asset": net.payment_asset_address(),
                "price": str(int(agent.price_atomic)),
                "payTo": wallet_address,
            },
            "erc8004": {
                "registry": f"{net.caip2()}:{net.identity_registry()}",
                "agentId": agent.erc8004_agent_id,
            },
        },
    }


async def handle_a2a(slug: str, req: JsonRpcRequest, x_payment: str | None) -> dict[str, Any]:
    raise NotImplementedYet("gateway.a2a")

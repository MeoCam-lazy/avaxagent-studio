"""ERC-8004 registration service."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain import network as net
from app.control_plane.agents.models import AgentStatus
from app.control_plane.agents.service import AgentService
from app.control_plane.registry.schemas import (
    NetworkInfo,
    RegistrationRequest,
    RegistrationStatus,
)
from app.core.config import settings
from app.core.queue import REGISTER_AGENT, get_queue


def network_info() -> NetworkInfo:
    """Static chain facts (works without DB / RPC)."""
    nc = net.network()
    return NetworkInfo(
        network=nc.name,
        chain_id=nc.chain_id,
        rpc_url=nc.rpc_url,
        explorer_url=nc.explorer_url,
        identity_registry=net.identity_registry(),
        payment_asset=settings.payment_asset,
        payment_asset_address=net.payment_asset_address(),
        erc8183_enabled=settings.commerce_enabled,
    )


class RegistryService:
    def __init__(self, session: AsyncSession, queue: Any | None = None) -> None:
        self.session = session
        self.queue = queue

    async def register(
        self, owner_id: str, agent_id: uuid.UUID, req: RegistrationRequest
    ) -> RegistrationStatus:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.wallet_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "wallet_required"},
            )
        if agent.status not in (AgentStatus.PROVISIONING, AgentStatus.FAILED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "agent_not_provisioning"},
            )

        # Commit before enqueueing so the worker and the next status poll see
        # REGISTERING; otherwise a poll reports the old state and invites a
        # second register click (a second on-chain identity).
        agent.status = AgentStatus.REGISTERING
        await self.session.commit()

        try:
            queue = self.queue
            if queue is None:
                queue = await get_queue()
            await queue.enqueue_job(REGISTER_AGENT, str(agent.id))
        except Exception:
            agent.status = AgentStatus.FAILED
            await self.session.commit()
            raise

        return await self.status(owner_id, agent_id)

    async def status(self, owner_id: str, agent_id: uuid.UUID) -> RegistrationStatus:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.erc8004_agent_id is not None:
            state = "registered"
        elif agent.status == AgentStatus.REGISTERING:
            state = "pending"
        elif agent.status == AgentStatus.FAILED:
            state = "failed"
        else:
            state = "not_registered"

        tx_hash = agent.registration_tx_hash
        explorer_url = f"{net.network().explorer_url}/tx/{tx_hash}" if tx_hash else None

        return RegistrationStatus(
            chain_id=net.chain_id(),
            identity_registry=net.identity_registry(),
            state=state,
            erc8004_agent_id=agent.erc8004_agent_id,
            agent_uri=agent.agent_uri,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
        )

    async def refresh_uri(self, owner_id: str, agent_id: uuid.UUID) -> RegistrationStatus:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.erc8004_agent_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "not_registered"},
            )

        queue = self.queue
        if queue is None:
            queue = await get_queue()
        await queue.enqueue_job(REGISTER_AGENT, str(agent.id))

        return await self.status(owner_id, agent_id)

"""Ledger aggregation and payouts.

Payout = ERC-20 ``transfer`` of the payment asset from the agent wallet
(Turnkey signer, gas in AVAX) to the owner's address, after reserving the
studio fee (sent to ``STUDIO_TREASURY_ADDRESS``).
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain import network as net
from app.control_plane.agents.models import Agent
from app.control_plane.billing.ledger import aggregate_balances, balances
from app.control_plane.billing.models import LedgerEntry
from app.control_plane.billing.schemas import (
    EarningsSummary,
    FeeSchedule,
    LedgerEntryRead,
    PayoutCreate,
    PayoutRead,
)
from app.core.config import settings
from app.core.errors import NotImplementedYet


def fee_schedule() -> FeeSchedule:
    return FeeSchedule(
        studio_fee_bps=settings.studio_fee_bps,
        payment_asset=settings.payment_asset,
        payment_asset_address=net.payment_asset_address(),
        chain_id=net.chain_id(),
    )


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self, owner_id: str, agent_id: uuid.UUID | None) -> EarningsSummary:
        if agent_id is not None:
            agent = await self.session.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.owner_id == owner_id.lower(),
                    Agent.deleted_at.is_(None),
                )
            )
            if agent.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail={"error": "agent_not_found"})
            return await balances(self.session, agent_id)

        res = await self.session.execute(
            select(Agent.id).where(
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
        )
        agent_ids = list(res.scalars().all())
        return await aggregate_balances(self.session, agent_ids, summary_agent_id=None)

    async def ledger(
        self, owner_id: str, agent_id: uuid.UUID | None, limit: int, offset: int
    ) -> list[LedgerEntryRead]:
        limit = min(limit, 200)
        stmt = (
            select(LedgerEntry)
            .join(Agent, LedgerEntry.agent_id == Agent.id)
            .where(
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if agent_id is not None:
            # Verify ownership
            agent = await self.session.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.owner_id == owner_id.lower(),
                    Agent.deleted_at.is_(None),
                )
            )
            if agent.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail={"error": "agent_not_found"})
            stmt = stmt.where(LedgerEntry.agent_id == agent_id)

        res = await self.session.execute(stmt)
        entries = res.scalars().all()
        return [LedgerEntryRead.model_validate(e) for e in entries]

    async def request_payout(self, owner_id: str, req: PayoutCreate) -> PayoutRead:
        raise NotImplementedYet("billing.request_payout")

    async def list_payouts(self, owner_id: str) -> list[PayoutRead]:
        raise NotImplementedYet("billing.list_payouts")

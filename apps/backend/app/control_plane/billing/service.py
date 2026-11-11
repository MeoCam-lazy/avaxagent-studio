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
from web3 import Web3

from app.chain import network as net
from app.control_plane.agents.models import Agent
from app.control_plane.billing.ledger import aggregate_balances, balances
from app.control_plane.billing.models import (
    LedgerEntry,
    LedgerKind,
    Payout,
    PayoutStatus,
)
from app.control_plane.billing.schemas import (
    EarningsSummary,
    FeeSchedule,
    LedgerEntryRead,
    PayoutCreate,
    PayoutRead,
)
from app.core.config import settings


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
        stmt = (
            select(Agent)
            .where(
                Agent.id == req.agent_id,
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
            .with_for_update()
        )
        agent = (await self.session.execute(stmt)).scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=404, detail={"error": "agent_not_found"})

        summary = await balances(self.session, req.agent_id)
        if req.amount_atomic > summary.withdrawable_atomic:
            await self.session.rollback()  # release the row lock now
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "insufficient_balance",
                    "withdrawable": summary.withdrawable_atomic,
                },
            )

        # The executor transfers ``asset``, so it must be the token address,
        # not the ``PAYMENT_ASSET`` alias ("USDC").
        asset = net.payment_asset_address()
        payout = Payout(
            agent_id=req.agent_id,
            owner_id=owner_id.lower(),
            destination=Web3.to_checksum_address(req.destination),
            asset=asset,
            amount_atomic=req.amount_atomic,
            status=PayoutStatus.REQUESTED,
        )
        self.session.add(payout)
        await self.session.flush()

        ledger_entry = LedgerEntry(
            agent_id=req.agent_id,
            job_id=None,
            kind=LedgerKind.PAYOUT,
            asset=asset,
            amount_atomic=req.amount_atomic,
            chain_id=agent.chain_id,
            tx_hash=None,
            log_index=None,
            payout_id=payout.id,
        )
        self.session.add(ledger_entry)
        await self.session.commit()
        await self.session.refresh(payout)

        return PayoutRead.model_validate(payout)

    async def list_payouts(
        self, owner_id: str, agent_id: uuid.UUID | None = None
    ) -> list[PayoutRead]:
        stmt = (
            select(Payout)
            .where(Payout.owner_id == owner_id.lower())
            .order_by(Payout.created_at.desc())
        )
        if agent_id is not None:
            stmt = stmt.where(Payout.agent_id == agent_id)
        res = await self.session.execute(stmt)
        return [PayoutRead.model_validate(p) for p in res.scalars().all()]

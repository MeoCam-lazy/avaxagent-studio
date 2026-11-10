from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.billing.models import (
    LedgerEntry,
    LedgerKind,
    Payout,
    PayoutStatus,
)
from app.control_plane.billing.schemas import EarningsSummary
from app.control_plane.jobs.models import Job
from app.core.config import settings


def studio_fee(amount: int) -> int:
    return amount * settings.studio_fee_bps // 10_000


async def record_income(
    db: AsyncSession,
    *,
    job: Job,
    amount: int,
    asset: str,
    tx_hash: str | None,
    log_index: int | None = None,
) -> None:
    existing = await db.execute(
        select(LedgerEntry).where(
            LedgerEntry.job_id == job.id,
            LedgerEntry.kind == LedgerKind.INCOME,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    income_entry = LedgerEntry(
        agent_id=job.agent_id,
        job_id=job.id,
        kind=LedgerKind.INCOME,
        asset=asset,
        amount_atomic=amount,
        chain_id=job.chain_id,
        tx_hash=tx_hash,
        log_index=log_index,
    )
    fee = studio_fee(amount)
    fee_entry = LedgerEntry(
        agent_id=job.agent_id,
        job_id=job.id,
        kind=LedgerKind.STUDIO_FEE,
        asset=asset,
        amount_atomic=fee,
        chain_id=job.chain_id,
        tx_hash=tx_hash,
        log_index=log_index,
    )

    db.add(income_entry)
    db.add(fee_entry)
    await db.flush()


async def aggregate_balances(
    db: AsyncSession,
    agent_ids: list[uuid.UUID],
    summary_agent_id: uuid.UUID | None = None,
) -> EarningsSummary:
    if not agent_ids:
        return EarningsSummary(
            agent_id=summary_agent_id,
            gross_income_atomic=0,
            studio_fees_atomic=0,
            paid_out_atomic=0,
            withdrawable_atomic=0,
        )

    ledger_stmt = (
        select(LedgerEntry.kind, func.coalesce(func.sum(LedgerEntry.amount_atomic), 0))
        .where(LedgerEntry.agent_id.in_(agent_ids))
        .group_by(LedgerEntry.kind)
    )
    ledger_res = await db.execute(ledger_stmt)
    ledger_map = dict(ledger_res.all())
    gross_income = int(ledger_map.get(LedgerKind.INCOME, 0))
    studio_fees = int(ledger_map.get(LedgerKind.STUDIO_FEE, 0))

    payout_stmt = (
        select(Payout.status, func.coalesce(func.sum(Payout.amount_atomic), 0))
        .where(Payout.agent_id.in_(agent_ids))
        .group_by(Payout.status)
    )
    payout_res = await db.execute(payout_stmt)
    payout_map = dict(payout_res.all())

    paid_out = int(payout_map.get(PayoutStatus.CONFIRMED, 0))
    reserved = (
        paid_out
        + int(payout_map.get(PayoutStatus.REQUESTED, 0))
        + int(payout_map.get(PayoutStatus.SUBMITTED, 0))
    )
    withdrawable = max(0, gross_income - studio_fees - reserved)

    return EarningsSummary(
        agent_id=summary_agent_id,
        gross_income_atomic=gross_income,
        studio_fees_atomic=studio_fees,
        paid_out_atomic=paid_out,
        withdrawable_atomic=withdrawable,
    )


async def balances(db: AsyncSession, agent_id: uuid.UUID) -> EarningsSummary:
    return await aggregate_balances(db, [agent_id], summary_agent_id=agent_id)

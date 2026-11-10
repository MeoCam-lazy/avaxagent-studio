from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_job

from app.control_plane.billing.ledger import balances, record_income, studio_fee
from app.control_plane.billing.models import LedgerEntry, LedgerKind, Payout, PayoutStatus


def test_fee_floor():
    assert studio_fee(1) == 0
    assert studio_fee(1_000_000) == 50_000
    assert studio_fee(19) == 0


@pytest.mark.asyncio
async def test_record_income_writes_income_and_fee(db: AsyncSession):
    agent = await make_agent(db)
    job = await make_job(db, agent)
    await record_income(
        db,
        job=job,
        amount=1_000_000,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        tx_hash="0x" + "a" * 64,
        log_index=0,
    )

    stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.job_id == job.id)
        .order_by(LedgerEntry.created_at.asc())
    )
    res = await db.execute(stmt)
    entries = res.scalars().all()
    assert len(entries) == 2
    income = next(e for e in entries if e.kind == LedgerKind.INCOME)
    fee = next(e for e in entries if e.kind == LedgerKind.STUDIO_FEE)
    assert income.amount_atomic == 1_000_000
    assert fee.amount_atomic == 50_000
    assert income.agent_id == agent.id
    assert fee.agent_id == agent.id


@pytest.mark.asyncio
async def test_record_income_idempotent(db: AsyncSession):
    agent = await make_agent(db)
    job = await make_job(db, agent)
    for _ in range(2):
        await record_income(
            db,
            job=job,
            amount=1_000_000,
            asset="0x5425890298aed601595a70AB815c96711a31Bc65",
            tx_hash="0x" + "b" * 64,
            log_index=0,
        )
    stmt = select(LedgerEntry).where(LedgerEntry.job_id == job.id)
    res = await db.execute(stmt)
    entries = res.scalars().all()
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_withdrawable_excludes_failed_payouts(db: AsyncSession):
    agent = await make_agent(db)
    job = await make_job(db, agent)
    await record_income(
        db,
        job=job,
        amount=1_000_000,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        tx_hash="0x" + "c" * 64,
        log_index=0,
    )

    payout_confirmed = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x1111111111111111111111111111111111111111",
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=100_000,
        status=PayoutStatus.CONFIRMED,
    )
    payout_requested = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x1111111111111111111111111111111111111111",
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=50_000,
        status=PayoutStatus.REQUESTED,
    )
    payout_failed = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x1111111111111111111111111111111111111111",
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=200_000,
        status=PayoutStatus.FAILED,
    )
    db.add_all([payout_confirmed, payout_requested, payout_failed])
    await db.flush()

    bal = await balances(db, agent.id)
    assert bal.gross_income_atomic == 1_000_000
    assert bal.studio_fees_atomic == 50_000
    assert bal.paid_out_atomic == 100_000
    assert bal.withdrawable_atomic == 800_000


@pytest.mark.asyncio
async def test_summary_all_agents_of_owner(api: httpx.AsyncClient, db: AsyncSession):
    agent1 = await make_agent(db, slug="sum-agent-1")
    agent2 = await make_agent(db, slug="sum-agent-2")
    job1 = await make_job(db, agent1)
    job2 = await make_job(db, agent2)

    await record_income(db, job=job1, amount=1_000_000, asset="USDC", tx_hash="0x1", log_index=0)
    await record_income(db, job=job2, amount=2_000_000, asset="USDC", tx_hash="0x2", log_index=0)

    other_agent = await make_agent(
        db, owner_id="0x9999999999999999999999999999999999999999", slug="other-sum"
    )
    other_job = await make_job(db, other_agent)
    await record_income(
        db, job=other_job, amount=5_000_000, asset="USDC", tx_hash="0x3", log_index=0
    )
    await db.commit()

    res = await api.get("/api/v1/billing/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] is None
    assert data["gross_income_atomic"] == 3_000_000
    assert data["studio_fees_atomic"] == 150_000
    assert data["withdrawable_atomic"] == 2_850_000

    res_agent1 = await api.get(f"/api/v1/billing/summary?agent_id={agent1.id}")
    assert res_agent1.status_code == 200
    data1 = res_agent1.json()
    assert data1["agent_id"] == str(agent1.id)
    assert data1["gross_income_atomic"] == 1_000_000
    assert data1["studio_fees_atomic"] == 50_000
    assert data1["withdrawable_atomic"] == 950_000

    res_other = await api.get(f"/api/v1/billing/summary?agent_id={other_agent.id}")
    assert res_other.status_code == 404


@pytest.mark.asyncio
async def test_ledger_returns_ordered_rows(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="ledger-agent")
    job = await make_job(db, agent)
    await record_income(db, job=job, amount=1_000_000, asset="USDC", tx_hash="0x10", log_index=0)
    await db.commit()

    res = await api.get("/api/v1/billing/ledger")
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 2
    assert {e["kind"] for e in entries} == {"income", "studio_fee"}

    res_agent = await api.get(f"/api/v1/billing/ledger?agent_id={agent.id}")
    assert res_agent.status_code == 200
    assert len(res_agent.json()) == 2

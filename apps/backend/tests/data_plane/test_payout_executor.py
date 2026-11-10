from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.ledger import balances
from app.control_plane.billing.models import LedgerEntry, LedgerKind, Payout, PayoutStatus
from app.control_plane.wallets.models import Wallet
from app.data_plane.settler.payouts import PayoutExecutor


@pytest.mark.asyncio
async def test_executor_submits_and_confirms(db: AsyncSession):
    wallet = Wallet(address="0x" + "11" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "aa" * 20,
        slug="agent-exec-1",
        name="Agent Exec 1",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    payout = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x" + "22" * 20,
        asset="USDC",
        amount_atomic=500_000,
        status=PayoutStatus.REQUESTED,
    )
    db.add(payout)

    ledger_entry = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.PAYOUT,
        asset="USDC",
        amount_atomic=500_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(ledger_entry)
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "ff" * 32

    executor = PayoutExecutor(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
    )

    processed = await executor.tick()
    assert processed == 1
    assert len(called) == 1
    assert called[0] == (wallet.address, "0x" + "22" * 20, 500_000)

    async with TestSessionLocal() as s:
        p = await s.get(Payout, payout.id)
        assert p.status == PayoutStatus.CONFIRMED
        assert p.tx_hash == "0x" + "ff" * 32

        entries = (
            (
                await s.execute(
                    select(LedgerEntry).where(
                        LedgerEntry.agent_id == agent.id,
                        LedgerEntry.kind == LedgerKind.PAYOUT,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1
        assert entries[0].tx_hash == "0x" + "ff" * 32


@pytest.mark.asyncio
async def test_executor_failure_restores_balance(db: AsyncSession):
    wallet = Wallet(address="0x" + "33" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "bb" * 20,
        slug="agent-exec-2",
        name="Agent Exec 2",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    # Initial gross income: 1_000_000
    income = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.INCOME,
        asset="USDC",
        amount_atomic=1_000_000,
        chain_id=43113,
        tx_hash="0x" + "11" * 32,
    )
    db.add(income)

    payout = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x" + "44" * 20,
        asset="USDC",
        amount_atomic=600_000,
        status=PayoutStatus.REQUESTED,
    )
    db.add(payout)

    payout_ledger = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.PAYOUT,
        asset="USDC",
        amount_atomic=600_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(payout_ledger)
    await db.commit()

    # Before tick: withdrawable is 400_000 (1_000_000 - 600_000 reserved)
    b_before = await balances(db, agent.id)
    assert b_before.withdrawable_atomic == 400_000

    async def failing_transfer(w, to, amount):
        raise RuntimeError("network timeout / reverted")

    executor = PayoutExecutor(
        session_factory=TestSessionLocal,
        transfer_fn=failing_transfer,
    )

    processed = await executor.tick()
    assert processed == 0

    async with TestSessionLocal() as s:
        p = await s.get(Payout, payout.id)
        assert p.status == PayoutStatus.FAILED

        # PAYOUT ledger entry was deleted
        entries = (
            (
                await s.execute(
                    select(LedgerEntry).where(
                        LedgerEntry.agent_id == agent.id,
                        LedgerEntry.kind == LedgerKind.PAYOUT,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 0

        # Withdrawable balance is restored to 1_000_000!
        b_after = await balances(s, agent.id)
        assert b_after.withdrawable_atomic == 1_000_000

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.wallets.models import Wallet
from app.core.config import settings
from app.data_plane.settler.fees import FeeSweeper


@pytest.mark.asyncio
async def test_sweeps_above_threshold(db: AsyncSession, monkeypatch):
    treasury = "0x" + "99" * 20
    monkeypatch.setattr(settings, "studio_treasury_address", treasury)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1_000_000)

    wallet = Wallet(address="0x" + "11" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "aa" * 20,
        slug="agent-fee-sweep-1",
        name="Agent Fee Sweep 1",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    e1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=600_000,
        chain_id=43113,
        tx_hash=None,
    )
    e2 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=500_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add_all([e1, e2])
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "aa" * 32

    sweeper = FeeSweeper(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
        get_native_balance_fn=lambda _: 10**18,
    )

    count = await sweeper.tick()
    assert count == 1
    assert len(called) == 1
    assert called[0] == (wallet.address, treasury, 1_100_000)

    # Check stamped rows
    async with TestSessionLocal() as session:
        entries = (
            (
                await session.execute(
                    select(LedgerEntry).where(
                        LedgerEntry.agent_id == agent.id,
                        LedgerEntry.kind == LedgerKind.STUDIO_FEE,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 2
        assert all(e.tx_hash == "0x" + "aa" * 32 for e in entries)


@pytest.mark.asyncio
async def test_below_threshold_noop(db: AsyncSession, monkeypatch):
    treasury = "0x" + "99" * 20
    monkeypatch.setattr(settings, "studio_treasury_address", treasury)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1_000_000)

    wallet = Wallet(address="0x" + "22" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "bb" * 20,
        slug="agent-fee-sweep-2",
        name="Agent Fee Sweep 2",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    e1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=500_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(e1)
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "bb" * 32

    sweeper = FeeSweeper(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
        get_native_balance_fn=lambda _: 10**18,
    )

    count = await sweeper.tick()
    assert count == 0
    assert len(called) == 0


@pytest.mark.asyncio
async def test_no_treasury_noop(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "studio_treasury_address", None)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1_000_000)

    wallet = Wallet(address="0x" + "33" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "cc" * 20,
        slug="agent-fee-sweep-3",
        name="Agent Fee Sweep 3",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    e1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=2_000_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(e1)
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "cc" * 32

    sweeper = FeeSweeper(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
        get_native_balance_fn=lambda _: 10**18,
    )

    count = await sweeper.tick()
    assert count == 0
    assert len(called) == 0


@pytest.mark.asyncio
async def test_low_avax_skips(db: AsyncSession, monkeypatch):
    treasury = "0x" + "99" * 20
    monkeypatch.setattr(settings, "studio_treasury_address", treasury)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1_000_000)

    wallet = Wallet(address="0x" + "44" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "dd" * 20,
        slug="agent-fee-sweep-4",
        name="Agent Fee Sweep 4",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    e1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=2_000_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(e1)
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "dd" * 32

    sweeper = FeeSweeper(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
        get_native_balance_fn=lambda _: 0,  # 0 AVAX
    )

    count = await sweeper.tick()
    assert count == 0
    assert len(called) == 0

    # Ensure still unstamped
    async with TestSessionLocal() as session:
        entry = (
            await session.execute(select(LedgerEntry).where(LedgerEntry.agent_id == agent.id))
        ).scalar_one()
        assert entry.tx_hash is None


@pytest.mark.asyncio
async def test_rows_stamped_once(db: AsyncSession, monkeypatch):
    treasury = "0x" + "99" * 20
    monkeypatch.setattr(settings, "studio_treasury_address", treasury)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1_000_000)

    wallet = Wallet(address="0x" + "55" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="0x" + "ee" * 20,
        slug="agent-fee-sweep-5",
        name="Agent Fee Sweep 5",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    e1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.STUDIO_FEE,
        asset="USDC",
        amount_atomic=1_500_000,
        chain_id=43113,
        tx_hash=None,
    )
    db.add(e1)
    await db.commit()

    called = []

    async def fake_transfer(w, to, amount):
        called.append((w.address, to, amount))
        return "0x" + "ee" * 32

    sweeper = FeeSweeper(
        session_factory=TestSessionLocal,
        transfer_fn=fake_transfer,
        get_native_balance_fn=lambda _: 10**18,
    )

    c1 = await sweeper.tick()
    assert c1 == 1
    assert len(called) == 1

    # Second tick: rows already stamped, should not sweep again
    c2 = await sweeper.tick()
    assert c2 == 0
    assert len(called) == 1


@pytest.mark.asyncio
async def test_settle_bot_tick_calls_both():
    from app.data_plane.settler.service import SettleBot

    payout_called = False
    fee_called = False

    class FakePayoutExecutor:
        async def tick(self):
            nonlocal payout_called
            payout_called = True
            return 0

    class FakeFeeSweeper:
        async def tick(self):
            nonlocal fee_called
            fee_called = True
            return 0

    bot = SettleBot(
        session_factory=TestSessionLocal,
        payout_executor=FakePayoutExecutor(),
        fee_sweeper=FakeFeeSweeper(),
    )
    await bot.tick()
    assert payout_called is True
    assert fee_called is True

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal
from tests.factories import make_agent, make_job, make_wallet
from tests.fakes import FakeChainReader, FakeTokenSender

from app.chain import network as net
from app.control_plane.billing.ledger import balances, record_income
from app.control_plane.billing.models import FeeSweep, LedgerEntry, LedgerKind, PayoutStatus
from app.core.config import settings
from app.data_plane.settler.fees import FeeSweeper

TREASURY = "0x2222222222222222222222222222222222222222"
# 5% of 20 USDC = 1 USDC = FEE_SWEEP_MIN_ATOMIC.
INCOME_AT_THRESHOLD = 20_000_000


@pytest.fixture(autouse=True)
def _treasury(monkeypatch):
    monkeypatch.setattr(settings, "studio_treasury_address", TREASURY)


async def _agent_with_income(db: AsyncSession, *incomes: int):
    """Agent with a wallet and one x402 job per income, booked like the gateway does."""
    wallet = await make_wallet(db)
    agent = await make_agent(db, wallet_id=wallet.id)
    for i, amount in enumerate(incomes):
        job = await make_job(db, agent)
        await record_income(
            db,
            job=job,
            amount=amount,
            asset=net.payment_asset_address(),
            tx_hash="0x" + f"{i + 1:064x}",  # real fee rows carry the payment tx hash
        )
    await db.commit()
    return agent, wallet


def _sweeper(sender: FakeTokenSender, reader: FakeChainReader | None = None) -> FeeSweeper:
    return FeeSweeper(TestSessionLocal, sender, reader or FakeChainReader())


async def _fee_rows(agent_id):
    async with TestSessionLocal() as s:
        return (
            (
                await s.execute(
                    select(LedgerEntry).where(
                        LedgerEntry.agent_id == agent_id,
                        LedgerEntry.kind == LedgerKind.STUDIO_FEE,
                    )
                )
            )
            .scalars()
            .all()
        )


async def _sweeps(agent_id):
    async with TestSessionLocal() as s:
        return (
            (await s.execute(select(FeeSweep).where(FeeSweep.agent_id == agent_id)))
            .scalars()
            .all()
        )


@pytest.mark.asyncio
async def test_sweeps_above_threshold(db: AsyncSession):
    # Two jobs: fees 600_000 + 400_000 = 1_000_000.
    agent, wallet = await _agent_with_income(db, 12_000_000, 8_000_000)
    before = await balances(db, agent.id)
    sender = FakeTokenSender()

    await _sweeper(sender).tick()

    assert sender.calls == [(wallet.address, net.payment_asset_address(), TREASURY, 1_000_000)]
    [sweep] = await _sweeps(agent.id)
    assert sweep.status == PayoutStatus.CONFIRMED
    assert sweep.tx_hash == sender.tx_hash
    assert sweep.amount_atomic == 1_000_000
    rows = await _fee_rows(agent.id)
    assert {r.fee_sweep_id for r in rows} == {sweep.id}
    # Provenance is kept: each fee row still points at its payment tx.
    assert {r.tx_hash for r in rows} == {"0x" + f"{1:064x}", "0x" + f"{2:064x}"}
    # Fees were never the owner's money: withdrawable does not move.
    async with TestSessionLocal() as s:
        assert (await balances(s, agent.id)).withdrawable_atomic == before.withdrawable_atomic


@pytest.mark.asyncio
async def test_below_threshold_noop(db: AsyncSession):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD - 20)  # fee 999_999
    sender = FakeTokenSender()

    await _sweeper(sender).tick()

    assert sender.calls == []
    assert await _sweeps(agent.id) == []


@pytest.mark.asyncio
async def test_no_treasury_noop(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "studio_treasury_address", None)
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender()

    await _sweeper(sender).tick()

    assert sender.calls == []
    assert await _sweeps(agent.id) == []


@pytest.mark.asyncio
async def test_low_avax_skips(db: AsyncSession, caplog):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender(gas_cost_wei=10**15)

    await _sweeper(sender, FakeChainReader(native_balance=10**15 - 1)).tick()

    assert sender.calls == []
    assert await _sweeps(agent.id) == []
    assert any("AVAX" in r.message and r.levelname == "WARNING" for r in caplog.records)


@pytest.mark.asyncio
async def test_rows_stamped_once(db: AsyncSession):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender()
    sweeper = _sweeper(sender)

    await sweeper.tick()
    await sweeper.tick()

    assert len(sender.calls) == 1
    assert len(await _sweeps(agent.id)) == 1


@pytest.mark.asyncio
async def test_failed_sweep_releases_rows_for_retry(db: AsyncSession):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender(mode="revert")
    sweeper = _sweeper(sender)

    await sweeper.tick()
    [failed] = await _sweeps(agent.id)
    assert failed.status == PayoutStatus.FAILED
    assert all(r.fee_sweep_id is None for r in await _fee_rows(agent.id))

    sender.mode = "ok"
    await sweeper.tick()
    confirmed = [s for s in await _sweeps(agent.id) if s.status == PayoutStatus.CONFIRMED]
    assert len(confirmed) == 1
    assert {r.fee_sweep_id for r in await _fee_rows(agent.id)} == {confirmed[0].id}


@pytest.mark.asyncio
async def test_pending_sweep_reconciles_without_resend(db: AsyncSession):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender(mode="pending")
    sweeper = _sweeper(sender)

    await sweeper.tick()
    [sweep] = await _sweeps(agent.id)
    assert sweep.status == PayoutStatus.SUBMITTED
    assert sweep.tx_hash == sender.tx_hash

    await sweeper.tick()  # still no receipt: no second transfer
    assert len(sender.calls) == 1

    sender.receipts[sender.tx_hash] = 1
    await sweeper.tick()
    [sweep] = await _sweeps(agent.id)
    assert sweep.status == PayoutStatus.CONFIRMED
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_new_fees_after_sweep_accumulate_separately(db: AsyncSession):
    agent, _ = await _agent_with_income(db, INCOME_AT_THRESHOLD)
    sender = FakeTokenSender()
    sweeper = _sweeper(sender)
    await sweeper.tick()

    job = await make_job(db, agent)
    await record_income(
        db, job=job, amount=1_000_000, asset=net.payment_asset_address(), tx_hash="0x" + "f" * 64
    )
    await db.commit()
    await sweeper.tick()  # 50_000 unswept: below threshold

    assert len(sender.calls) == 1
    unswept = [r for r in await _fee_rows(agent.id) if r.fee_sweep_id is None]
    assert [r.amount_atomic for r in unswept] == [50_000]


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

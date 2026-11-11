from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal
from tests.factories import make_agent, make_job, make_wallet
from tests.fakes import FakeTokenSender

from app.control_plane.billing.ledger import balances, record_income
from app.control_plane.billing.models import LedgerEntry, LedgerKind, Payout, PayoutStatus
from app.control_plane.billing.schemas import PayoutCreate
from app.control_plane.billing.service import BillingService
from app.data_plane.settler.payouts import PayoutExecutor

DEST = "0x1111111111111111111111111111111111111111"
USDC = "0x5425890298aed601595a70AB815c96711a31Bc65"


async def _requested_payout(db: AsyncSession, amount: int = 500_000, with_wallet: bool = True):
    """Agent with 1 USDC income (950_000 withdrawable) and one requested payout."""
    wallet = await make_wallet(db) if with_wallet else None
    agent = await make_agent(db, wallet_id=wallet.id if wallet else None)
    job = await make_job(db, agent)
    await record_income(db, job=job, amount=1_000_000, asset=USDC, tx_hash=None)
    await db.commit()
    read = await BillingService(db).request_payout(
        agent.owner_id, PayoutCreate(agent_id=agent.id, destination=DEST, amount_atomic=amount)
    )
    return wallet, read.id


async def _state(payout_id):
    async with TestSessionLocal() as s:
        payout = await s.get(Payout, payout_id)
        ledger = (
            await s.execute(select(LedgerEntry).where(LedgerEntry.payout_id == payout_id))
        ).scalar_one_or_none()
        bal = await balances(s, payout.agent_id)
        return payout, ledger, bal


@pytest.mark.asyncio
async def test_executor_submits_and_confirms(db: AsyncSession):
    wallet, payout_id = await _requested_payout(db)
    sender = FakeTokenSender()

    await PayoutExecutor(TestSessionLocal, sender).tick()

    payout, ledger, bal = await _state(payout_id)
    assert payout.status == PayoutStatus.CONFIRMED
    assert payout.tx_hash == sender.tx_hash
    assert sender.calls == [(wallet.address, payout.asset, DEST, 500_000)]
    assert ledger.kind == LedgerKind.PAYOUT
    assert ledger.tx_hash == sender.tx_hash
    assert bal.paid_out_atomic == 500_000
    assert bal.withdrawable_atomic == 450_000

    # A confirmed payout is never sent again.
    await PayoutExecutor(TestSessionLocal, sender).tick()
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_executor_failure_restores_balance(db: AsyncSession):
    _, payout_id = await _requested_payout(db)
    sender = FakeTokenSender(mode="revert")

    await PayoutExecutor(TestSessionLocal, sender).tick()

    payout, ledger, bal = await _state(payout_id)
    assert payout.status == PayoutStatus.FAILED
    assert ledger is None
    assert bal.withdrawable_atomic == 950_000


@pytest.mark.asyncio
async def test_executor_pending_reconciles_by_receipt(db: AsyncSession):
    _, payout_id = await _requested_payout(db)
    sender = FakeTokenSender(mode="pending")
    executor = PayoutExecutor(TestSessionLocal, sender)

    await executor.tick()
    payout, _, bal = await _state(payout_id)
    assert payout.status == PayoutStatus.SUBMITTED
    assert payout.tx_hash == sender.tx_hash
    assert bal.withdrawable_atomic == 450_000  # still reserved

    await executor.tick()  # receipt unknown: stays submitted, no resend
    assert (await _state(payout_id))[0].status == PayoutStatus.SUBMITTED

    sender.receipts[sender.tx_hash] = 1
    await executor.tick()
    payout, ledger, _ = await _state(payout_id)
    assert payout.status == PayoutStatus.CONFIRMED
    assert ledger.tx_hash == sender.tx_hash
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_executor_pending_then_reverted_restores_balance(db: AsyncSession):
    _, payout_id = await _requested_payout(db)
    sender = FakeTokenSender(mode="pending")
    executor = PayoutExecutor(TestSessionLocal, sender)
    await executor.tick()

    sender.receipts[sender.tx_hash] = 0
    await executor.tick()
    payout, ledger, bal = await _state(payout_id)
    assert payout.status == PayoutStatus.FAILED
    assert ledger is None
    assert bal.withdrawable_atomic == 950_000


@pytest.mark.asyncio
async def test_executor_never_resends_unknown_submission(db: AsyncSession):
    """A crash after claiming leaves SUBMITTED with no hash: hold funds, never resend."""
    _, payout_id = await _requested_payout(db)
    async with TestSessionLocal() as s:
        payout = await s.get(Payout, payout_id)
        payout.status = PayoutStatus.SUBMITTED
        await s.commit()
    sender = FakeTokenSender()

    await PayoutExecutor(TestSessionLocal, sender).tick()

    assert sender.calls == []
    payout, _, bal = await _state(payout_id)
    assert payout.status == PayoutStatus.SUBMITTED
    assert bal.withdrawable_atomic == 450_000


@pytest.mark.asyncio
async def test_executor_missing_wallet_fails_payout(db: AsyncSession):
    _, payout_id = await _requested_payout(db, amount=1, with_wallet=False)
    sender = FakeTokenSender()

    await PayoutExecutor(TestSessionLocal, sender).tick()

    payout, ledger, _ = await _state(payout_id)
    assert payout.status == PayoutStatus.FAILED
    assert ledger is None
    assert sender.calls == []


@pytest.mark.asyncio
async def test_default_executor_sends_real_erc20_transfer(db: AsyncSession, monkeypatch):
    """No injected sender: the executor must build a real ERC-20 transfer of the
    payment token (regression: it raised NotImplementedError, and the payout's
    asset was the "USDC" alias, not a token address)."""
    from avaxagent.erc20 import MinimalERC20Client

    from app.chain import network as net
    from app.data_plane.settler import transfers

    wallet, payout_id = await _requested_payout(db)
    signed_for: list[str] = []
    sent: list[tuple[str, str, int]] = []

    class _Signer:
        address = wallet.address

    def fake_agent_signer(w):
        signed_for.append(w.address)
        return _Signer()

    def fake_transfer(self, to, amount):
        sent.append((self.address, to, amount))
        return {"transactionHash": bytes.fromhex("cc" * 32), "status": 1}

    monkeypatch.setattr(transfers, "agent_signer", fake_agent_signer)
    monkeypatch.setattr(MinimalERC20Client, "transfer", fake_transfer)

    await PayoutExecutor(TestSessionLocal).tick()

    payout, ledger, _ = await _state(payout_id)
    assert payout.status == PayoutStatus.CONFIRMED
    assert payout.tx_hash == "0x" + "cc" * 32
    assert signed_for == [wallet.address]
    assert sent == [(net.payment_asset_address(), DEST, 500_000)]

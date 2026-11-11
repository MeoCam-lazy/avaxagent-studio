"""Payout executor: sends requested withdrawals on-chain, at most once.

Lifecycle of a ``Payout``::

    requested --claim--> submitted --receipt ok--> confirmed
                             |  \\--revert/error--> failed (PAYOUT ledger row dropped)
                             \\--no receipt yet--> stays submitted, reconciled by tx hash

A payout is claimed (``requested -> submitted``, committed) *before* the
transfer is broadcast. If the process dies mid-send, the payout stays
``submitted`` and is never sent again automatically: funds stay reserved until
an operator reconciles it. Double-paying is worse than a stuck withdrawal.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.control_plane.agents.models import Agent
from app.control_plane.billing.models import LedgerEntry, Payout, PayoutStatus
from app.control_plane.wallets.models import Wallet
from app.data_plane.settler.transfers import Erc20TokenSender, TokenSender, TransferPending
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Claim:
    payout_id: uuid.UUID
    wallet: Wallet
    asset: str
    destination: str
    amount: int


class PayoutExecutor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
        sender: TokenSender | None = None,
        batch_size: int = 20,
    ) -> None:
        self.session_factory = session_factory
        self._sender = sender
        self.batch_size = batch_size

    @property
    def sender(self) -> TokenSender:
        if self._sender is None:
            self._sender = Erc20TokenSender()
        return self._sender

    async def tick(self) -> None:
        await self._reconcile_submitted()
        for _ in range(self.batch_size):
            claim = await self._claim_next()
            if claim is None:
                return
            if claim is not _SKIPPED:
                await self._send(claim)

    async def _claim_next(self) -> _Claim | object | None:
        """Move the oldest requested payout to submitted, in its own transaction."""
        async with self.session_factory() as db, db.begin():
            payout = (
                await db.execute(
                    select(Payout)
                    .where(Payout.status == PayoutStatus.REQUESTED)
                    .order_by(Payout.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if payout is None:
                return None

            wallet = (
                await db.execute(
                    select(Wallet)
                    .join(Agent, Agent.wallet_id == Wallet.id)
                    .where(Agent.id == payout.agent_id)
                )
            ).scalar_one_or_none()
            if wallet is None:
                log.warning("payout %s: agent %s has no wallet", payout.id, payout.agent_id)
                await _mark_failed(db, payout)
                return _SKIPPED

            payout.status = PayoutStatus.SUBMITTED
            return _Claim(
                payout_id=payout.id,
                wallet=wallet,
                asset=payout.asset,
                destination=payout.destination,
                amount=payout.amount_atomic,
            )

    async def _send(self, claim: _Claim) -> None:
        try:
            tx_hash = await asyncio.to_thread(
                self.sender.transfer, claim.wallet, claim.asset, claim.destination, claim.amount
            )
        except TransferPending as pending:
            log.warning("payout %s pending as %s", claim.payout_id, pending.tx_hash)
            await self._finish(claim.payout_id, PayoutStatus.SUBMITTED, pending.tx_hash)
        except Exception:
            log.exception("payout %s failed", claim.payout_id)
            await self._finish(claim.payout_id, PayoutStatus.FAILED, None)
        else:
            await self._finish(claim.payout_id, PayoutStatus.CONFIRMED, tx_hash)

    async def _reconcile_submitted(self) -> None:
        async with self.session_factory() as db:
            submitted = (
                (await db.execute(select(Payout).where(Payout.status == PayoutStatus.SUBMITTED)))
                .scalars()
                .all()
            )

        for payout in submitted:
            if payout.tx_hash is None:
                log.warning(
                    "payout %s is submitted with no tx hash (send interrupted); "
                    "funds stay reserved until an operator reconciles it",
                    payout.id,
                )
                continue
            status = await asyncio.to_thread(self.sender.receipt_status, payout.tx_hash)
            if status == 1:
                await self._finish(payout.id, PayoutStatus.CONFIRMED, payout.tx_hash)
            elif status == 0:
                log.warning("payout %s reverted on-chain: %s", payout.id, payout.tx_hash)
                await self._finish(payout.id, PayoutStatus.FAILED, payout.tx_hash)

    async def _finish(
        self, payout_id: uuid.UUID, status: PayoutStatus, tx_hash: str | None
    ) -> None:
        """Apply the send outcome to a submitted payout and its ledger row."""
        async with self.session_factory() as db, db.begin():
            payout = (
                await db.execute(select(Payout).where(Payout.id == payout_id).with_for_update())
            ).scalar_one()
            if payout.status != PayoutStatus.SUBMITTED:
                return
            payout.tx_hash = tx_hash
            if status == PayoutStatus.FAILED:
                await _mark_failed(db, payout)
            elif status == PayoutStatus.CONFIRMED:
                payout.status = PayoutStatus.CONFIRMED
                await db.execute(
                    update(LedgerEntry)
                    .where(LedgerEntry.payout_id == payout_id)
                    .values(tx_hash=tx_hash)
                )


_SKIPPED = object()


async def _mark_failed(db: AsyncSession, payout: Payout) -> None:
    """Fail the payout and drop its PAYOUT ledger row, freeing the funds."""
    payout.status = PayoutStatus.FAILED
    await db.execute(delete(LedgerEntry).where(LedgerEntry.payout_id == payout.id))

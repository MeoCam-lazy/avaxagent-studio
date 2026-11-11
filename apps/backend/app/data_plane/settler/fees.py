"""Studio fee sweep: batch each agent's unswept STUDIO_FEE rows to the treasury.

Fees are booked when income lands in the agent wallet; they stay there until
their sum reaches ``FEE_SWEEP_MIN_ATOMIC``, then one transfer moves them all.

Like payouts, a sweep is claimed before it is broadcast: a ``FeeSweep`` row is
created as ``submitted`` and the fee rows are linked to it (``fee_sweep_id``)
in one committed transaction. A crash mid-send leaves the rows claimed, so
they are never swept twice. A failed sweep unlinks its rows for the next tick.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chain import network as net
from app.chain.reader import ChainReader, get_chain_reader
from app.control_plane.agents.models import Agent
from app.control_plane.billing.models import FeeSweep, LedgerEntry, LedgerKind, PayoutStatus
from app.control_plane.wallets.models import Wallet
from app.core.config import settings
from app.data_plane.settler.transfers import Erc20TokenSender, TokenSender, TransferPending
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Claim:
    sweep_id: uuid.UUID
    wallet: Wallet
    asset: str
    destination: str
    amount: int


def _unswept_fees(asset: str):
    return (
        LedgerEntry.kind == LedgerKind.STUDIO_FEE,
        LedgerEntry.fee_sweep_id.is_(None),
        func.lower(LedgerEntry.asset) == asset.lower(),
    )


class FeeSweeper:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
        sender: TokenSender | None = None,
        reader: ChainReader | None = None,
    ) -> None:
        self.session_factory = session_factory
        self._sender = sender
        self._reader = reader

    @property
    def sender(self) -> TokenSender:
        if self._sender is None:
            self._sender = Erc20TokenSender()
        return self._sender

    @property
    def reader(self) -> ChainReader:
        if self._reader is None:
            self._reader = get_chain_reader()
        return self._reader

    async def tick(self) -> None:
        # Pending sweeps are reconciled even if the treasury was unset since.
        await self._reconcile_submitted()

        treasury = settings.studio_treasury_address
        if not treasury:
            return
        asset = net.payment_asset_address()

        async with self.session_factory() as db:
            due = (
                await db.execute(
                    select(LedgerEntry.agent_id, func.sum(LedgerEntry.amount_atomic))
                    .where(*_unswept_fees(asset))
                    .group_by(LedgerEntry.agent_id)
                    .having(func.sum(LedgerEntry.amount_atomic) >= settings.fee_sweep_min_atomic)
                )
            ).all()

        for agent_id, amount in due:
            try:
                claim = await self._claim(agent_id, asset, treasury, int(amount))
            except Exception:
                log.exception("fee sweep for agent %s could not start", agent_id)
                continue
            if claim is not None:
                await self._send(claim)

    async def _claim(
        self, agent_id: uuid.UUID, asset: str, treasury: str, amount: int
    ) -> _Claim | None:
        async with self.session_factory() as db:
            wallet = (
                await db.execute(
                    select(Wallet)
                    .join(Agent, Agent.wallet_id == Wallet.id)
                    .where(Agent.id == agent_id)
                )
            ).scalar_one_or_none()
        if wallet is None:
            log.warning("fee sweep skipped: agent %s has no wallet", agent_id)
            return None

        # Chain reads stay outside the transaction so no row lock waits on RPC.
        gas_cost = await asyncio.to_thread(
            self.sender.estimate_gas_cost_wei, wallet, asset, treasury, amount
        )
        avax = await asyncio.to_thread(self.reader.native_balance, wallet.address)
        if avax < gas_cost:
            log.warning(
                "fee sweep skipped: agent %s wallet %s has %s wei AVAX, needs ~%s for gas",
                agent_id,
                wallet.address,
                avax,
                gas_cost,
            )
            return None

        async with self.session_factory() as db, db.begin():
            rows = (
                (
                    await db.execute(
                        select(LedgerEntry)
                        .where(LedgerEntry.agent_id == agent_id, *_unswept_fees(asset))
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )
            total = sum(int(r.amount_atomic) for r in rows)
            if total < settings.fee_sweep_min_atomic:
                return None
            sweep = FeeSweep(
                agent_id=agent_id,
                destination=treasury,
                asset=asset,
                amount_atomic=total,
                status=PayoutStatus.SUBMITTED,
            )
            db.add(sweep)
            await db.flush()
            for row in rows:
                row.fee_sweep_id = sweep.id
            return _Claim(sweep.id, wallet, asset, treasury, total)

    async def _send(self, claim: _Claim) -> None:
        try:
            tx_hash = await asyncio.to_thread(
                self.sender.transfer, claim.wallet, claim.asset, claim.destination, claim.amount
            )
        except TransferPending as pending:
            log.warning("fee sweep %s pending as %s", claim.sweep_id, pending.tx_hash)
            await self._finish(claim.sweep_id, PayoutStatus.SUBMITTED, pending.tx_hash)
        except Exception:
            log.exception("fee sweep %s failed", claim.sweep_id)
            await self._finish(claim.sweep_id, PayoutStatus.FAILED, None)
        else:
            await self._finish(claim.sweep_id, PayoutStatus.CONFIRMED, tx_hash)

    async def _reconcile_submitted(self) -> None:
        async with self.session_factory() as db:
            submitted = (
                (
                    await db.execute(
                        select(FeeSweep).where(FeeSweep.status == PayoutStatus.SUBMITTED)
                    )
                )
                .scalars()
                .all()
            )

        for sweep in submitted:
            if sweep.tx_hash is None:
                log.warning(
                    "fee sweep %s is submitted with no tx hash (send interrupted); "
                    "its fee rows stay claimed until an operator reconciles it",
                    sweep.id,
                )
                continue
            status = await asyncio.to_thread(self.sender.receipt_status, sweep.tx_hash)
            if status == 1:
                await self._finish(sweep.id, PayoutStatus.CONFIRMED, sweep.tx_hash)
            elif status == 0:
                log.warning("fee sweep %s reverted on-chain: %s", sweep.id, sweep.tx_hash)
                await self._finish(sweep.id, PayoutStatus.FAILED, sweep.tx_hash)

    async def _finish(
        self, sweep_id: uuid.UUID, status: PayoutStatus, tx_hash: str | None
    ) -> None:
        """Apply the send outcome to a submitted sweep and its fee rows."""
        async with self.session_factory() as db, db.begin():
            sweep = (
                await db.execute(select(FeeSweep).where(FeeSweep.id == sweep_id).with_for_update())
            ).scalar_one()
            if sweep.status != PayoutStatus.SUBMITTED:
                return
            sweep.tx_hash = tx_hash
            sweep.status = status
            if status == PayoutStatus.FAILED:
                await db.execute(
                    update(LedgerEntry)
                    .where(LedgerEntry.fee_sweep_id == sweep_id)
                    .values(fee_sweep_id=None)
                )

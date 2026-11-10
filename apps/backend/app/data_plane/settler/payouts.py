"""Payout execution worker.

Processes PayoutStatus.REQUESTED payouts:
1. Calls transfer_fn (or agent_signer(wallet)) to transfer USDC to payout.destination.
2. Updates Payout status -> SUBMITTED with tx_hash.
3. Once receipt confirms -> CONFIRMED, stamps PAYOUT ledger entry with tx_hash.
4. On failure/revert -> moves payout to FAILED and deletes the unconfirmed PAYOUT
   ledger entry in the same transaction so balance is restored.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.control_plane.agents.models import Agent
from app.control_plane.billing.models import LedgerEntry, LedgerKind, Payout, PayoutStatus
from app.control_plane.wallets.models import Wallet

log = logging.getLogger(__name__)


class PayoutExecutor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
        transfer_fn: Callable[[Wallet, str, int], Any] | None = None,
        confirm_fn: Callable[[str], Any] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.transfer_fn = transfer_fn
        self.confirm_fn = confirm_fn

    async def _send_transfer(self, wallet: Wallet, to: str, amount: int) -> str:
        if self.transfer_fn is not None:
            res = self.transfer_fn(wallet, to, amount)
            if inspect.isawaitable(res):
                return await res
            return str(res)
        raise NotImplementedError("transfer_fn required or live agent_signer")

    async def _confirm_tx(self, tx_hash: str) -> bool:
        if self.confirm_fn is not None:
            res = self.confirm_fn(tx_hash)
            if inspect.isawaitable(res):
                return await res
            return bool(res)
        return True

    async def tick(self) -> int:
        processed = 0
        async with self.session_factory() as db:
            stmt = (
                select(Payout, Wallet)
                .join(Agent, Payout.agent_id == Agent.id)
                .join(Wallet, Agent.wallet_id == Wallet.id)
                .where(Payout.status == PayoutStatus.REQUESTED)
                .order_by(Payout.created_at.asc())
            )
            res = await db.execute(stmt)
            rows = res.all()

        for payout, wallet in rows:
            p_id = payout.id
            p_agent_id = payout.agent_id
            p_amount = payout.amount_atomic
            p_dest = payout.destination

            async with self.session_factory() as db:
                p = await db.get(Payout, p_id)
                if not p or p.status != PayoutStatus.REQUESTED:
                    continue

                try:
                    tx_hash = await self._send_transfer(wallet, p_dest, p_amount)
                    p.status = PayoutStatus.SUBMITTED
                    p.tx_hash = tx_hash
                    await db.flush()

                    confirmed = await self._confirm_tx(tx_hash)
                    if confirmed:
                        p.status = PayoutStatus.CONFIRMED
                        ledger_stmt = select(LedgerEntry).where(
                            LedgerEntry.agent_id == p_agent_id,
                            LedgerEntry.kind == LedgerKind.PAYOUT,
                            LedgerEntry.amount_atomic == p_amount,
                            LedgerEntry.tx_hash.is_(None),
                        )
                        entry = (await db.execute(ledger_stmt)).scalars().first()
                        if entry:
                            entry.tx_hash = tx_hash
                    else:
                        raise RuntimeError("Transaction confirmation failed")

                    await db.commit()
                    processed += 1
                except Exception as exc:
                    await db.rollback()
                    log.warning("Payout execution failed for payout %s: %s", p_id, exc)
                    async with self.session_factory() as fail_db:
                        failed_p = await fail_db.get(Payout, p_id)
                        if failed_p:
                            failed_p.status = PayoutStatus.FAILED
                            del_stmt = delete(LedgerEntry).where(
                                LedgerEntry.agent_id == p_agent_id,
                                LedgerEntry.kind == LedgerKind.PAYOUT,
                                LedgerEntry.amount_atomic == p_amount,
                                LedgerEntry.tx_hash.is_(None),
                            )
                            await fail_db.execute(del_stmt)
                            await fail_db.commit()

        return processed

"""Studio fee sweeper worker.

Batches accumulated studio fees from agent wallets to the platform treasury.
Per agent, it sums STUDIO_FEE ledger entries where tx_hash IS NULL.
If sum >= FEE_SWEEP_MIN_ATOMIC and STUDIO_TREASURY_ADDRESS is configured:
1. Verifies the agent wallet has sufficient native AVAX for gas. If not, skips and logs a warning.
2. Transfers the accumulated fee sum from agent wallet to studio treasury address.
3. Stamps all swept STUDIO_FEE rows with the sweep tx_hash.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.control_plane.agents.models import Agent
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.wallets.models import Wallet
from app.core.config import settings

log = logging.getLogger(__name__)

# Default minimum gas buffer: ~0.001 AVAX (10^15 wei)
DEFAULT_MIN_GAS_WEI = 10**15


class FeeSweeper:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
        transfer_fn: Callable[[Wallet, str, int], Any] | None = None,
        get_native_balance_fn: Callable[[str], Any] | None = None,
        min_gas_wei: int = DEFAULT_MIN_GAS_WEI,
    ) -> None:
        self.session_factory = session_factory
        self.transfer_fn = transfer_fn
        self.get_native_balance_fn = get_native_balance_fn
        self.min_gas_wei = min_gas_wei

    async def _send_transfer(self, wallet: Wallet, to: str, amount: int) -> str:
        if self.transfer_fn is not None:
            res = self.transfer_fn(wallet, to, amount)
            if inspect.isawaitable(res):
                return await res
            return str(res)
        raise NotImplementedError("transfer_fn or live agent_signer required")

    async def _get_native_balance(self, address: str) -> int:
        if self.get_native_balance_fn is not None:
            res = self.get_native_balance_fn(address)
            if inspect.isawaitable(res):
                return await res
            return int(res)
        return 10**18  # default assumption if not provided

    async def tick(self) -> int:
        treasury = settings.studio_treasury_address
        if not treasury:
            log.debug("Studio treasury address not configured, skipping fee sweep")
            return 0

        threshold = settings.fee_sweep_min_atomic
        processed = 0

        async with self.session_factory() as db:
            stmt = (
                select(Agent, Wallet, func.sum(LedgerEntry.amount_atomic).label("total_fee"))
                .join(Wallet, Agent.wallet_id == Wallet.id)
                .join(LedgerEntry, LedgerEntry.agent_id == Agent.id)
                .where(
                    LedgerEntry.kind == LedgerKind.STUDIO_FEE,
                    LedgerEntry.tx_hash.is_(None),
                )
                .group_by(Agent.id, Wallet.id)
                .having(func.sum(LedgerEntry.amount_atomic) >= threshold)
            )
            res = await db.execute(stmt)
            candidates = res.all()

        for agent, wallet, total_fee in candidates:
            total_atomic = int(total_fee)
            native_bal = await self._get_native_balance(wallet.address)
            if native_bal < self.min_gas_wei:
                log.warning(
                    "Agent %s wallet %s low AVAX balance (%s < %s wei), skip sweep",
                    agent.id,
                    wallet.address,
                    native_bal,
                    self.min_gas_wei,
                )
                continue

            async with self.session_factory() as db:
                try:
                    tx_hash = await self._send_transfer(wallet, treasury, total_atomic)
                    update_stmt = (
                        update(LedgerEntry)
                        .where(
                            LedgerEntry.agent_id == agent.id,
                            LedgerEntry.kind == LedgerKind.STUDIO_FEE,
                            LedgerEntry.tx_hash.is_(None),
                        )
                        .values(tx_hash=tx_hash)
                    )
                    await db.execute(update_stmt)
                    await db.commit()
                    processed += 1
                    log.info(
                        "Swept %s fee from agent %s to treasury %s (tx: %s)",
                        total_atomic,
                        agent.id,
                        treasury,
                        tx_hash,
                    )
                except Exception as exc:
                    await db.rollback()
                    log.error("Failed to sweep fee for agent %s: %s", agent.id, exc)

        return processed

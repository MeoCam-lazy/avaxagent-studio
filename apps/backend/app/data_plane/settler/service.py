"""Settle loop.

* Payouts: executes REQUESTED withdrawals from agent wallets to owners
  (``app.data_plane.settler.payouts``).
* Studio fees: sweeps accumulated fees to STUDIO_TREASURY_ADDRESS when above
  threshold (``app.data_plane.settler.fees``).
* erc8183 mode: for SUBMITTED jobs past the OptimisticPolicy dispute window,
  calls the permissionless router.settle(jobId) (gated until deployed in Task 23).
* x402 mode: payment is settled on-chain by the facilitator at request time.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.data_plane.settler.fees import FeeSweeper
from app.data_plane.settler.payouts import PayoutExecutor
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


class SettleBot:
    poll_interval_s: float = 30.0

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession]
        | Callable[[], AsyncSession]
        | None = None,
        payout_executor: PayoutExecutor | None = None,
        fee_sweeper: FeeSweeper | None = None,
    ) -> None:
        self.session_factory = session_factory or SessionLocal
        self.payout_executor = payout_executor or PayoutExecutor(self.session_factory)
        self.fee_sweeper = fee_sweeper or FeeSweeper(self.session_factory)

    async def tick(self) -> None:
        await self.payout_executor.tick()
        await self.fee_sweeper.tick()
        if settings.commerce_enabled:
            # Task 23 ERC-8183 dispute window & router.settle
            pass

    async def run(self) -> None:
        log.info("settle bot starting (erc8183 enabled=%s)", settings.commerce_enabled)
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("settle tick failed")
            await asyncio.sleep(self.poll_interval_s)

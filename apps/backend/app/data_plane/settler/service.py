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
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.control_plane.jobs.models import Job, JobStatus
from app.core.config import settings
from app.core.queue import RUN_JOB, get_queue
from app.data_plane.settler.escrow import EscrowSettler
from app.data_plane.settler.fees import FeeSweeper
from app.data_plane.settler.payouts import PayoutExecutor
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


class SettleBot:
    poll_interval_s: float = 30.0
    stuck_funded_after_s: int = 60

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession]
        | Callable[[], AsyncSession]
        | None = None,
        payout_executor: PayoutExecutor | None = None,
        fee_sweeper: FeeSweeper | None = None,
        escrow_settler: EscrowSettler | None = None,
        queue: Any | None = None,
    ) -> None:
        self.session_factory = session_factory or SessionLocal
        self.payout_executor = payout_executor or PayoutExecutor(self.session_factory)
        self.fee_sweeper = fee_sweeper or FeeSweeper(self.session_factory)
        self.escrow_settler = escrow_settler or EscrowSettler(self.session_factory)
        self.queue = queue

    async def tick(self) -> None:
        await self._requeue_stuck_funded_jobs()
        await self.payout_executor.tick()
        await self.fee_sweeper.tick()
        if settings.commerce_enabled:
            await self.escrow_settler.tick()

    async def _requeue_stuck_funded_jobs(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.stuck_funded_after_s)
        async with self.session_factory() as db:
            stmt = select(Job.id).where(
                Job.status == JobStatus.FUNDED,
                Job.created_at < cutoff,
            )
            stuck_ids = [str(jid) for jid in (await db.execute(stmt)).scalars().all()]

        if not stuck_ids:
            return 0

        q = self.queue
        owns_queue = q is None
        try:
            if q is None:
                q = await get_queue()
            for jid in stuck_ids:
                await q.enqueue_job(RUN_JOB, jid)
            log.info("Re-enqueued %d stuck FUNDED job(s)", len(stuck_ids))
            return len(stuck_ids)
        except Exception:
            log.warning("Could not re-enqueue stuck FUNDED jobs; will retry next tick")
            return 0
        finally:
            if owns_queue and q is not None and hasattr(q, "aclose"):
                await q.aclose()

    async def run(self) -> None:
        log.info("settle bot starting (erc8183 enabled=%s)", settings.commerce_enabled)
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("settle tick failed")
            await asyncio.sleep(self.poll_interval_s)

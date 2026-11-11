"""ERC-8183 escrow settlement executor for ``SettleBot``.

Polls ``SUBMITTED`` ``erc8183`` jobs, checks ``OptimisticPolicy.check(jobId, b"")``,
and once the verdict is decided calls permissionless ``EvaluatorRouter.settle(jobId)``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chain.commerce import PolicyVerdict, erc8183_client
from app.chain.signers import relayer_signer
from app.control_plane.billing.ledger import record_income
from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import Job, JobStatus
from app.core.config import SettlementMode, settings
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


class EscrowSettler:
    """Settles ``SUBMITTED`` ERC-8183 jobs whose policy dispute window has resolved."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession]
        | Callable[[], AsyncSession]
        | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.session_factory = session_factory or SessionLocal
        self.client_factory = client_factory or (lambda: erc8183_client(relayer_signer()))

    async def tick(self) -> int:
        if not settings.commerce_enabled:
            return 0

        async with self.session_factory() as db:
            stmt = select(Job.id).where(
                Job.settlement_mode == SettlementMode.ERC8183,
                Job.status == JobStatus.SUBMITTED,
                Job.chain_job_id.is_not(None),
            )
            job_ids = list((await db.execute(stmt)).scalars().all())

        if not job_ids:
            return 0

        client = self.client_factory()
        settled_count = 0

        for jid in job_ids:
            try:
                if await self._settle_one(jid, client):
                    settled_count += 1
            except Exception:
                log.exception("Failed to settle ERC-8183 job %s", jid)

        return settled_count

    async def _settle_one(self, job_id: uuid.UUID, client: Any) -> bool:
        async with self.session_factory() as db:
            stmt = (
                select(Job)
                .where(
                    Job.id == job_id,
                    Job.settlement_mode == SettlementMode.ERC8183,
                    Job.status == JobStatus.SUBMITTED,
                )
                .with_for_update(skip_locked=True)
            )
            job = (await db.execute(stmt)).scalar_one_or_none()
            if job is None or job.chain_job_id is None:
                return False

            chain_job_id = int(job.chain_job_id)
            verdict, _reason = await asyncio.to_thread(client.policy_verdict, chain_job_id)
            if verdict == int(PolicyVerdict.PENDING):
                return False

            tx_hash = await asyncio.to_thread(client.settle, chain_job_id)
            job.settle_tx_hash = tx_hash

            if verdict == int(PolicyVerdict.APPROVED):
                job.status = JobStatus.SETTLED
                await add_event(db, job, "settled", tx_hash=tx_hash)
                await record_income(
                    db,
                    job=job,
                    amount=int(job.amount_atomic),
                    asset=job.asset,
                    tx_hash=tx_hash,
                )
            elif verdict == int(PolicyVerdict.REJECTED):
                job.status = JobStatus.REFUNDED
                await add_event(db, job, "refunded", tx_hash=tx_hash)
            else:
                raise RuntimeError(f"Unexpected policy verdict {verdict} for job {chain_job_id}")

            await db.commit()
            return True

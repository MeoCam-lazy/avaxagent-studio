from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.agents.models import Agent
from app.control_plane.jobs.models import Job, JobEvent, JobStatus
from app.control_plane.jobs.schemas import JobDeliverable, JobEventRead, JobRead
from app.data_plane.storage.service import get_storage

log = logging.getLogger(__name__)


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        owner_id: str,
        agent_id: uuid.UUID | None,
        status: JobStatus | None,
        limit: int,
        offset: int,
    ) -> list[JobRead]:
        limit = min(limit, 200)
        stmt = (
            select(Job)
            .join(Agent, Job.agent_id == Agent.id)
            .where(
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if agent_id is not None:
            stmt = stmt.where(Job.agent_id == agent_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)

        res = await self.session.execute(stmt)
        jobs = res.scalars().all()
        return [JobRead.model_validate(j) for j in jobs]

    async def get(self, owner_id: str, job_id: uuid.UUID) -> JobRead:
        return JobRead.model_validate(await self._get_owned(owner_id, job_id))

    async def deliverable(self, owner_id: str, job_id: uuid.UUID) -> JobDeliverable:
        """Stored deliverable for the owner; file:// and ipfs:// URIs are not browser-readable."""
        job = await self._get_owned(owner_id, job_id)
        if not job.deliverable_uri:
            raise HTTPException(status_code=404, detail={"error": "deliverable_not_ready"})
        try:
            content = await get_storage().download(job.deliverable_uri)
        except Exception:
            log.exception("deliverable download failed for job %s", job.id)
            raise HTTPException(
                status_code=502, detail={"error": "deliverable_unavailable"}
            ) from None
        return JobDeliverable(uri=job.deliverable_uri, hash=job.deliverable_hash, content=content)

    async def _get_owned(self, owner_id: str, job_id: uuid.UUID) -> Job:
        stmt = (
            select(Job)
            .join(Agent, Job.agent_id == Agent.id)
            .where(
                Job.id == job_id,
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
        )
        res = await self.session.execute(stmt)
        job = res.scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=404, detail={"error": "job_not_found"})
        return job

    async def events(self, owner_id: str, job_id: uuid.UUID) -> list[JobEventRead]:
        await self._get_owned(owner_id, job_id)

        stmt = (
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc())
        )
        res = await self.session.execute(stmt)
        events = res.scalars().all()
        return [JobEventRead.model_validate(e) for e in events]

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.agents.models import Agent
from app.control_plane.jobs.models import Job, JobEvent, JobStatus
from app.control_plane.jobs.schemas import JobEventRead, JobRead


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
        return JobRead.model_validate(job)

    async def events(self, owner_id: str, job_id: uuid.UUID) -> list[JobEventRead]:
        await self.get(owner_id, job_id)

        stmt = (
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc())
        )
        res = await self.session.execute(stmt)
        events = res.scalars().all()
        return [JobEventRead.model_validate(e) for e in events]

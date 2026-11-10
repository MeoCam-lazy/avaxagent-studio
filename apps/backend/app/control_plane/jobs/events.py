from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.jobs.models import Job, JobEvent


async def add_event(
    db: AsyncSession,
    job: Job,
    type: str,
    message: str = "",
    **data: Any,
) -> JobEvent:
    event = JobEvent(
        job_id=job.id,
        type=type,
        message=message,
        data=dict(data),
    )
    db.add(event)
    await db.flush()
    return event

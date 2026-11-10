from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_job

from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import JobStatus


@pytest.mark.asyncio
async def test_list_filters_by_agent_and_status(api: httpx.AsyncClient, db: AsyncSession):
    agent1 = await make_agent(db, slug="agent-1")
    agent2 = await make_agent(db, slug="agent-2")

    job1 = await make_job(db, agent1, status=JobStatus.FUNDED)
    job2 = await make_job(db, agent1, status=JobStatus.RUNNING)
    job3 = await make_job(db, agent2, status=JobStatus.FUNDED)

    # Filter by agent1
    res1 = await api.get(f"/api/v1/jobs?agent_id={agent1.id}")
    assert res1.status_code == 200
    ids1 = [item["id"] for item in res1.json()]
    assert str(job1.id) in ids1
    assert str(job2.id) in ids1
    assert str(job3.id) not in ids1

    # Filter by status running
    res2 = await api.get("/api/v1/jobs?status=running")
    assert res2.status_code == 200
    ids2 = [item["id"] for item in res2.json()]
    assert str(job2.id) in ids2
    assert str(job1.id) not in ids2

    # Filter by agent1 AND status funded
    res3 = await api.get(f"/api/v1/jobs?agent_id={agent1.id}&status=funded")
    assert res3.status_code == 200
    ids3 = [item["id"] for item in res3.json()]
    assert str(job1.id) in ids3
    assert str(job2.id) not in ids3
    assert str(job3.id) not in ids3


@pytest.mark.asyncio
async def test_other_owner_job_404(api: httpx.AsyncClient, db: AsyncSession):
    other_agent = await make_agent(
        db, owner_id="0x9999999999999999999999999999999999999999", slug="other-agent"
    )
    other_job = await make_job(db, other_agent)

    # list excludes other owner's jobs
    list_res = await api.get("/api/v1/jobs")
    assert list_res.status_code == 200
    ids = [item["id"] for item in list_res.json()]
    assert str(other_job.id) not in ids

    # get returns 404
    get_res = await api.get(f"/api/v1/jobs/{other_job.id}")
    assert get_res.status_code == 404

    # events returns 404
    events_res = await api.get(f"/api/v1/jobs/{other_job.id}/events")
    assert events_res.status_code == 404


@pytest.mark.asyncio
async def test_events_chronological(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="events-agent")
    job = await make_job(db, agent)

    await add_event(db, job, "funded", message="Job funded")
    await add_event(db, job, "llm_started", message="LLM started")
    await add_event(db, job, "settled", message="Job settled")
    await db.commit()

    res = await api.get(f"/api/v1/jobs/{job.id}/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) == 3
    assert [e["type"] for e in events] == ["funded", "llm_started", "settled"]


@pytest.mark.asyncio
async def test_limit_capped_200(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="limit-agent")
    for _ in range(5):
        await make_job(db, agent)

    # Request limit=500 should be capped at 200 (validation or service cap)
    # router has limit: int = Query(default=50, le=200), so requesting 250 returns 422
    res_over = await api.get("/api/v1/jobs?limit=250")
    assert res_over.status_code == 422

    res_capped = await api.get("/api/v1/jobs?limit=200")
    assert res_capped.status_code == 200
    assert len(res_capped.json()) == 5

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_wallet
from tests.fakes import FakeQueue

from app.control_plane.agents.models import AgentStatus
from app.control_plane.registry.agent_uri import build_agent_uri
from app.core.config import settings
from app.core.queue import REGISTER_AGENT, get_queue
from app.main import app


@pytest.fixture
def fake_queue():
    q = FakeQueue()
    app.dependency_overrides[get_queue] = lambda: q
    yield q
    app.dependency_overrides.pop(get_queue, None)


@pytest.mark.asyncio
async def test_register_requires_wallet_409(api: httpx.AsyncClient, db: AsyncSession):
    # Agent without wallet
    agent = await make_agent(db, status=AgentStatus.DRAFT)
    res = await api.post(f"/api/v1/agents/{agent.id}/registration", json={})
    assert res.status_code == 409
    assert res.json() == {"error": "wallet_required"}


@pytest.mark.asyncio
async def test_register_enqueues_and_sets_registering(
    api: httpx.AsyncClient, db: AsyncSession, fake_queue: FakeQueue
):
    agent = await make_agent(db, status=AgentStatus.PROVISIONING)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.flush()

    res = await api.post(f"/api/v1/agents/{agent.id}/registration", json={})
    assert res.status_code == 202
    data = res.json()
    assert data["state"] == "pending"

    await db.refresh(agent)
    assert agent.status == AgentStatus.REGISTERING
    assert len(fake_queue.enqueued) == 1
    fn, args, _ = fake_queue.enqueued[0]
    assert fn == REGISTER_AGENT
    assert args[0] == str(agent.id)


@pytest.mark.asyncio
async def test_agent_uri_contains_gateway_endpoint(db: AsyncSession):
    agent = await make_agent(db, slug="my-cool-agent")
    uri = build_agent_uri(agent)
    assert uri.startswith("data:application/json;base64,")
    expected_endpoint = (
        f"{settings.public_gateway_url}/agents/{agent.slug}/.well-known/agent-card.json"
    )
    import base64
    import json

    b64_content = uri.split(",", 1)[1]
    parsed = json.loads(base64.b64decode(b64_content).decode("utf-8"))
    endpoints = [s["endpoint"] for s in parsed.get("services", [])]
    assert expected_endpoint in endpoints


@pytest.mark.asyncio
async def test_status_of_unregistered_agent(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, status=AgentStatus.DRAFT)
    res = await api.get(f"/api/v1/agents/{agent.id}/registration")
    assert res.status_code == 200
    assert res.json()["state"] == "not_registered"


@pytest.mark.asyncio
async def test_failed_registration_can_be_retried(
    api: httpx.AsyncClient, db: AsyncSession, fake_queue: FakeQueue
):
    agent = await make_agent(db, status=AgentStatus.FAILED)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.flush()

    assert (await api.get(f"/api/v1/agents/{agent.id}/registration")).json()["state"] == "failed"
    res = await api.post(f"/api/v1/agents/{agent.id}/registration", json={})
    assert res.status_code == 202
    assert res.json()["state"] == "pending"
    assert len(fake_queue.enqueued) == 1


@pytest.mark.asyncio
async def test_register_is_committed(
    api: httpx.AsyncClient, db: AsyncSession, fake_queue: FakeQueue
):
    from tests.conftest import TestSessionLocal

    from app.control_plane.agents.models import Agent

    agent = await make_agent(db, status=AgentStatus.PROVISIONING)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.commit()

    res = await api.post(f"/api/v1/agents/{agent.id}/registration", json={})
    assert res.status_code == 202

    async with TestSessionLocal() as s:
        saved = await s.get(Agent, agent.id)
    assert saved.status == AgentStatus.REGISTERING


@pytest.mark.asyncio
async def test_enqueue_failure_marks_failed_for_retry(api: httpx.AsyncClient, db: AsyncSession):
    from tests.conftest import TestSessionLocal

    from app.control_plane.agents.models import Agent

    class BrokenQueue:
        async def enqueue_job(self, *args, **kwargs):
            raise ConnectionError("redis down")

    app.dependency_overrides[get_queue] = lambda: BrokenQueue()
    try:
        agent = await make_agent(db, status=AgentStatus.PROVISIONING)
        wallet = await make_wallet(db)
        agent.wallet_id = wallet.id
        await db.commit()

        with pytest.raises(ConnectionError):
            await api.post(f"/api/v1/agents/{agent.id}/registration", json={})
    finally:
        app.dependency_overrides.pop(get_queue, None)

    async with TestSessionLocal() as s:
        saved = await s.get(Agent, agent.id)
    assert saved.status == AgentStatus.FAILED

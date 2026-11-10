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

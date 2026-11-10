from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_wallet

from app.control_plane.agents.models import AgentStatus
from app.core.config import settings
from app.data_plane.gateway.main import app as gateway_app
from app.db.session import get_session


@pytest_asyncio.fixture
async def gateway_api(db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db

    gateway_app.dependency_overrides[get_session] = _override_get_session
    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    gateway_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_card_for_active_agent(gateway_api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(
        db,
        status=AgentStatus.ACTIVE,
        slug="active-card-agent",
        name="Active Card Agent",
        description="A great agent",
        price_atomic=2_000_000,
        erc8004_agent_id=123,
    )
    wallet = await make_wallet(db, address="0x1234567890123456789012345678901234567890")
    agent.wallet_id = wallet.id
    await db.commit()

    res = await gateway_api.get(f"/agents/{agent.slug}/.well-known/agent-card.json")
    assert res.status_code == 200
    card = res.json()
    assert card["name"] == "Active Card Agent"
    assert card["url"] == f"{settings.public_gateway_url}/agents/{agent.slug}/a2a"
    assert card["capabilities"] == {"streaming": False}
    assert card["defaultInputModes"] == ["text"]
    assert card["defaultOutputModes"] == ["text"]

    ext_x402 = card["extensions"]["x402"]
    assert ext_x402["payTo"] == wallet.address
    assert ext_x402["price"] == "2000000"

    ext_8004 = card["extensions"]["erc8004"]
    assert ext_8004["agentId"] == 123


@pytest.mark.asyncio
async def test_unknown_slug_404(gateway_api: httpx.AsyncClient):
    res = await gateway_api.get("/agents/non-existent-agent-slug/.well-known/agent-card.json")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_draft_agent_404(gateway_api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, status=AgentStatus.DRAFT, slug="draft-agent")
    res = await gateway_api.get(f"/agents/{agent.slug}/.well-known/agent-card.json")
    assert res.status_code == 404

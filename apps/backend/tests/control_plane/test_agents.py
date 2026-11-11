from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_job

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.jobs.models import JobStatus
from app.core.config import settings


@pytest.mark.asyncio
async def test_create_returns_draft(api: httpx.AsyncClient):
    payload = {
        "slug": "my-first-agent",
        "name": "My First Agent",
        "description": "Test description",
        "price_atomic": 1_000_000,
        "is_public": True,
    }
    res = await api.post("/api/v1/agents", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["slug"] == "my-first-agent"
    assert data["status"] == "draft"
    assert data["chain_id"] == 43113
    assert data["price_atomic"] == 1_000_000
    assert data["is_public"] is True


@pytest.mark.asyncio
async def test_duplicate_slug_409(api: httpx.AsyncClient):
    payload = {
        "slug": "duplicate-slug",
        "name": "Duplicate Slug",
    }
    res1 = await api.post("/api/v1/agents", json=payload)
    assert res1.status_code == 201

    res2 = await api.post("/api/v1/agents", json=payload)
    assert res2.status_code == 409
    assert res2.json() == {"error": "slug_taken"}


@pytest.mark.asyncio
async def test_list_only_own_agents(api: httpx.AsyncClient, db: AsyncSession):
    # Default api user is 0x000000000000000000000000000000000000dead
    agent1 = await make_agent(db, slug="own-agent-1")
    agent2 = await make_agent(db, slug="own-agent-2")
    # Agent belonging to someone else
    await make_agent(db, owner_id="0x9999999999999999999999999999999999999999", slug="other-agent")

    res = await api.get("/api/v1/agents")
    assert res.status_code == 200
    slugs = [item["slug"] for item in res.json()]
    assert agent1.slug in slugs
    assert agent2.slug in slugs
    assert "other-agent" not in slugs


@pytest.mark.asyncio
async def test_get_other_owner_404(api: httpx.AsyncClient, db: AsyncSession):
    other_agent = await make_agent(
        db, owner_id="0x9999999999999999999999999999999999999999", slug="other-owner-agent"
    )
    res = await api.get(f"/api/v1/agents/{other_agent.id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_patch_updates_fields(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="patchable-agent", name="Old Name")
    patch_payload = {
        "name": "New Name",
        "description": "Updated description",
        "price_atomic": 2_500_000,
        "is_public": True,
    }
    res = await api.patch(f"/api/v1/agents/{agent.id}", json=patch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Updated description"
    assert data["price_atomic"] == 2_500_000
    assert data["is_public"] is True


@pytest.mark.asyncio
async def test_delete_soft_pauses(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="delete-agent", status=AgentStatus.ACTIVE)
    res = await api.delete(f"/api/v1/agents/{agent.id}")
    assert res.status_code == 204

    # Gone from list
    list_res = await api.get("/api/v1/agents")
    assert list_res.status_code == 200
    slugs = [item["slug"] for item in list_res.json()]
    assert agent.slug not in slugs

    # DB row has deleted_at set and status paused
    db_agent = (await db.execute(select(Agent).where(Agent.id == agent.id))).scalar_one()
    assert db_agent.deleted_at is not None
    assert db_agent.status == AgentStatus.PAUSED


@pytest.mark.asyncio
async def test_marketplace_public_active_only(api: httpx.AsyncClient, db: AsyncSession):
    # Active & Public -> Should be visible
    a_pub_act = await make_agent(db, slug="pub-act", is_public=True, status=AgentStatus.ACTIVE)
    # Draft & Public -> Should be excluded
    await make_agent(db, slug="pub-draft", is_public=True, status=AgentStatus.DRAFT)
    # Active & Private -> Should be excluded
    await make_agent(db, slug="priv-act", is_public=False, status=AgentStatus.ACTIVE)

    res = await api.get("/api/v1/marketplace/agents")
    assert res.status_code == 200
    slugs = [item["slug"] for item in res.json()]
    assert a_pub_act.slug in slugs
    assert "pub-draft" not in slugs
    assert "priv-act" not in slugs


@pytest.mark.asyncio
async def test_marketplace_search(api: httpx.AsyncClient, db: AsyncSession):
    await make_agent(
        db,
        slug="search-name",
        name="Crypto Trader Bot",
        is_public=True,
        status=AgentStatus.ACTIVE,
    )
    await make_agent(
        db,
        slug="search-desc",
        name="Random Bot",
        description="Analyzes crypto market trends",
        is_public=True,
        status=AgentStatus.ACTIVE,
    )
    await make_agent(
        db,
        slug="search-skill",
        name="Helper Bot",
        skills=["solidity-audit", "defi-analytics"],
        is_public=True,
        status=AgentStatus.ACTIVE,
    )

    res_name = await api.get("/api/v1/marketplace/agents?q=trader")
    assert res_name.status_code == 200
    slugs_name = [i["slug"] for i in res_name.json()]
    assert "search-name" in slugs_name
    assert "search-desc" not in slugs_name

    res_desc = await api.get("/api/v1/marketplace/agents?q=market")
    assert res_desc.status_code == 200
    slugs_desc = [i["slug"] for i in res_desc.json()]
    assert "search-desc" in slugs_desc

    res_skill = await api.get("/api/v1/marketplace/agents?q=solidity")
    assert res_skill.status_code == 200
    slugs_skill = [i["slug"] for i in res_skill.json()]
    assert "search-skill" in slugs_skill


@pytest.mark.asyncio
async def test_marketplace_card_url(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="card-test-agent", is_public=True, status=AgentStatus.ACTIVE)
    res = await api.get("/api/v1/marketplace/agents")
    assert res.status_code == 200
    item = next(i for i in res.json() if i["slug"] == agent.slug)
    expected_url = f"{settings.public_gateway_url}/agents/{agent.slug}/.well-known/agent-card.json"
    assert item["agent_card_url"] == expected_url


@pytest.mark.asyncio
async def test_marketplace_profile(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, slug="profile-agent", is_public=True, status=AgentStatus.ACTIVE)
    await make_job(db, agent, status=JobStatus.SETTLED)
    await make_job(db, agent, status=JobStatus.SETTLED)
    await make_job(db, agent, status=JobStatus.FAILED)
    await db.commit()

    res = await api.get("/api/v1/marketplace/agents/profile-agent")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "profile-agent"
    assert body["a2a_url"] == f"{settings.public_gateway_url}/agents/profile-agent/a2a"
    assert body["jobs_completed"] == 2
    assert "owner_id" not in body and "llm_config" not in body


@pytest.mark.asyncio
async def test_marketplace_profile_hides_unlisted(api: httpx.AsyncClient, db: AsyncSession):
    await make_agent(db, slug="hidden-draft", is_public=True, status=AgentStatus.DRAFT)
    await make_agent(db, slug="hidden-private", is_public=False, status=AgentStatus.ACTIVE)
    await db.commit()
    for slug in ("hidden-draft", "hidden-private", "nope"):
        res = await api.get(f"/api/v1/marketplace/agents/{slug}")
        assert res.status_code == 404, slug
        assert res.json()["error"] == "agent_not_found"

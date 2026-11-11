from __future__ import annotations

import re

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.agents.schemas import SLUG_PATTERN
from app.control_plane.billing.service import BillingService
from app.control_plane.jobs.models import Job
from app.seed import (
    DEFAULT_DEMO_OWNER,
    REFERENCE_AGENTS,
    _parse_args,
    seed_reference_agents,
)


def test_reference_agents_specs_are_valid() -> None:
    assert len(REFERENCE_AGENTS) == 3
    slugs = [spec.slug for spec in REFERENCE_AGENTS]
    assert len(set(slugs)) == 3
    for spec in REFERENCE_AGENTS:
        assert re.match(SLUG_PATTERN, spec.slug)
        assert spec.name
        assert spec.description
        assert len(spec.skills) >= 2
        assert spec.price_atomic > 0
        assert spec.demo_wallet_address.startswith("0x")
        assert len(spec.demo_wallet_address) == 42


def test_seed_cli_arg_parsing() -> None:
    default_args = _parse_args([])
    assert default_args.owner == DEFAULT_DEMO_OWNER
    assert default_args.agents_only is False
    assert default_args.live is False

    custom_args = _parse_args(["--owner", "0xabc", "--agents-only", "--live"])
    assert custom_args.owner == "0xabc"
    assert custom_args.agents_only is True
    assert custom_args.live is True


@pytest.mark.asyncio
async def test_seed_reference_agents_and_idempotency(
    db: AsyncSession, api: httpx.AsyncClient
) -> None:
    first = await seed_reference_agents(db)
    assert len(first.agents) == 3
    assert first.jobs_created == 3
    for agent in first.agents:
        assert agent.status == AgentStatus.ACTIVE
        assert agent.is_public is True
        assert agent.wallet_id is not None
        assert agent.agent_uri is not None

    # Running a second time is idempotent and creates no duplicate agents or jobs.
    second = await seed_reference_agents(db)
    assert len(second.agents) == 3
    assert second.jobs_created == 0

    total_agents = await db.scalar(select(func.count()).select_from(Agent))
    total_jobs = await db.scalar(select(func.count()).select_from(Job))
    assert total_agents == 3
    assert total_jobs == 3

    # Earnings summary matches 0.25 + 0.50 + 0.10 = 0.85 USDC gross (5% studio fee).
    summary = await BillingService(db).summary(DEFAULT_DEMO_OWNER, None)
    assert summary.gross_income_atomic == 850_000
    assert summary.studio_fees_atomic == 42_500
    assert summary.withdrawable_atomic == 807_500

    # Marketplace lists all 3 seeded reference agents.
    res = await api.get("/api/v1/marketplace/agents")
    assert res.status_code == 200
    listed_slugs = {row["slug"] for row in res.json()}
    assert listed_slugs == {spec.slug for spec in REFERENCE_AGENTS}

    for spec in REFERENCE_AGENTS:
        profile = await api.get(f"/api/v1/marketplace/agents/{spec.slug}")
        assert profile.status_code == 200
        assert profile.json()["jobs_completed"] == 1

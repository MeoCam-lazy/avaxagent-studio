from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal, auth_headers

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.ledger import record_income
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.db.session import get_session
from app.main import app


@pytest.mark.asyncio
async def test_payout_exceeds_withdrawable(api: AsyncClient, db: AsyncSession):
    owner = "0x" + "11" * 20
    agent = Agent(
        owner_id=owner.lower(),
        slug="agent-payout-1",
        name="Agent Payout 1",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
    )
    db.add(agent)
    await db.commit()

    # Income: 1_000_000, 5% fee: 50_000 -> withdrawable = 950_000
    await record_income(
        db,
        agent_id=agent.id,
        chain_id=agent.chain_id,
        amount=1_000_000,
        asset="USDC",
        tx_hash="0x" + "11" * 32,
        log_index=0,
    )
    await db.commit()

    dest = "0x" + "22" * 20
    resp = await api.post(
        "/api/v1/billing/payouts",
        json={"agent_id": str(agent.id), "destination": dest, "amount_atomic": 1_000_000},
        headers=auth_headers(owner),
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "insufficient_balance"
    assert data["withdrawable"] == 950_000


@pytest.mark.asyncio
async def test_payout_other_owner_404(api: AsyncClient, db: AsyncSession):
    owner_a = "0x" + "aa" * 20
    owner_b = "0x" + "bb" * 20
    agent = Agent(
        owner_id=owner_a.lower(),
        slug="agent-payout-owner",
        name="Agent Payout Owner",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
    )
    db.add(agent)
    await db.commit()

    dest = "0x" + "99" * 20
    resp = await api.post(
        "/api/v1/billing/payouts",
        json={"agent_id": str(agent.id), "destination": dest, "amount_atomic": 100_000},
        headers=auth_headers(owner_b),
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "agent_not_found"


@pytest.mark.asyncio
async def test_concurrent_payouts_never_overdraw(db: AsyncSession):
    owner = "0x" + "33" * 20
    agent = Agent(
        owner_id=owner.lower(),
        slug="agent-concurrent-payout",
        name="Agent Concurrent Payout",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
    )
    db.add(agent)
    await db.commit()

    income = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.INCOME,
        asset="USDC",
        amount_atomic=1_000_000,
        chain_id=agent.chain_id,
        tx_hash="0x" + "44" * 32,
        log_index=0,
    )
    db.add(income)
    await db.commit()

    agent_id = agent.id
    dest = "0x" + "55" * 20

    async def _independent_session() -> AsyncIterator[AsyncSession]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = _independent_session
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=auth_headers(owner)
        ) as c1,
        httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=auth_headers(owner)
        ) as c2,
    ):
        r1, r2 = await asyncio.gather(
            c1.post(
                "/api/v1/billing/payouts",
                json={"agent_id": str(agent_id), "destination": dest, "amount_atomic": 800_000},
            ),
            c2.post(
                "/api/v1/billing/payouts",
                json={"agent_id": str(agent_id), "destination": dest, "amount_atomic": 800_000},
            ),
        )
    app.dependency_overrides.pop(get_session, None)

    statuses = {r1.status_code, r2.status_code}
    assert statuses == {202, 422}


@pytest.mark.asyncio
async def test_payout_success_creates_payout_and_ledger(api: AsyncClient, db: AsyncSession):
    owner = "0x" + "66" * 20
    agent = Agent(
        owner_id=owner.lower(),
        slug="agent-payout-success",
        name="Agent Payout Success",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
    )
    db.add(agent)
    await db.commit()

    income = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.INCOME,
        asset="USDC",
        amount_atomic=2_000_000,
        chain_id=agent.chain_id,
        tx_hash="0x" + "66" * 32,
        log_index=0,
    )
    db.add(income)
    await db.commit()

    dest = "0x" + "77" * 20
    resp = await api.post(
        "/api/v1/billing/payouts",
        json={"agent_id": str(agent.id), "destination": dest, "amount_atomic": 500_000},
        headers=auth_headers(owner),
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "requested"
    assert data["amount_atomic"] == 500_000
    assert data["destination"] == dest

    # Verify list payouts
    list_resp = await api.get("/api/v1/billing/payouts", headers=auth_headers(owner))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

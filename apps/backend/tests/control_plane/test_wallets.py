from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent
from tests.fakes import FakeChainReader, FakeTurnkeyAdmin

from app.chain.reader import get_chain_reader
from app.control_plane.agents.models import AgentStatus
from app.control_plane.wallets.turnkey_admin import get_turnkey_admin
from app.main import app


@pytest.fixture(autouse=True)
def override_wallet_dependencies():
    fake_admin = FakeTurnkeyAdmin()
    fake_reader = FakeChainReader(
        native_balance=1_000_000_000_000_000_000,
        erc20_balance=100_000_000,
    )
    app.dependency_overrides[get_turnkey_admin] = lambda: fake_admin
    app.dependency_overrides[get_chain_reader] = lambda: fake_reader
    yield fake_admin, fake_reader
    app.dependency_overrides.pop(get_turnkey_admin, None)
    app.dependency_overrides.pop(get_chain_reader, None)


@pytest.mark.asyncio
async def test_provision_creates_wallet_and_moves_status(
    api: httpx.AsyncClient, db: AsyncSession
):
    agent = await make_agent(db, status=AgentStatus.DRAFT)

    res = await api.post(f"/api/v1/agents/{agent.id}/wallet")
    assert res.status_code == 201
    data = res.json()
    assert data["provider"] == "turnkey"
    assert data["address"].startswith("0x")
    assert data["turnkey_sub_org_id"] is not None

    # Verify agent updated
    await db.refresh(agent)
    assert agent.status == AgentStatus.PROVISIONING
    assert str(agent.wallet_id) == data["id"]


@pytest.mark.asyncio
async def test_provision_twice_409(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, status=AgentStatus.DRAFT)

    res1 = await api.post(f"/api/v1/agents/{agent.id}/wallet")
    assert res1.status_code == 201

    res2 = await api.post(f"/api/v1/agents/{agent.id}/wallet")
    assert res2.status_code == 409
    assert res2.json() == {"error": "wallet_exists"}


@pytest.mark.asyncio
async def test_provision_non_draft_409(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, status=AgentStatus.ACTIVE)

    res = await api.post(f"/api/v1/agents/{agent.id}/wallet")
    assert res.status_code == 409
    assert res.json() == {"error": "agent_not_in_draft"}


@pytest.mark.asyncio
async def test_policy_update_calls_admin(
    api: httpx.AsyncClient, db: AsyncSession, override_wallet_dependencies
):
    fake_admin, _ = override_wallet_dependencies
    agent = await make_agent(db, status=AgentStatus.DRAFT)
    prov_res = await api.post(f"/api/v1/agents/{agent.id}/wallet")
    assert prov_res.status_code == 201

    policy_payload = {
        "max_value_per_call_atomic": 2_000_000,
        "daily_budget_atomic": 100_000_000,
        "allowed_contracts": ["0x5425890298aed601595a70ab815c96711a31bc65"],
        "allow_erc8183": False,
    }
    update_res = await api.put(
        f"/api/v1/agents/{agent.id}/wallet/policy", json=policy_payload
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["policy"]["max_value_per_call_atomic"] == 2_000_000
    assert len(fake_admin.policies) > 0


@pytest.mark.asyncio
async def test_balances_from_reader(api: httpx.AsyncClient, db: AsyncSession):
    agent = await make_agent(db, status=AgentStatus.DRAFT)
    await api.post(f"/api/v1/agents/{agent.id}/wallet")

    res = await api.get(f"/api/v1/agents/{agent.id}/wallet/balances")
    assert res.status_code == 200
    data = res.json()
    assert data["avax_wei"] == 1_000_000_000_000_000_000
    assert data["payment_asset_atomic"] == 100_000_000


@pytest.mark.asyncio
async def test_wallet_other_owner_404(api: httpx.AsyncClient, db: AsyncSession):
    other_agent = await make_agent(
        db,
        owner_id="0x9999999999999999999999999999999999999999",
        status=AgentStatus.DRAFT,
        slug="other-wallet",
    )

    res_post = await api.post(f"/api/v1/agents/{other_agent.id}/wallet")
    assert res_post.status_code == 404

    res_get = await api.get(f"/api/v1/agents/{other_agent.id}/wallet")
    assert res_get.status_code == 404

    res_put = await api.put(
        f"/api/v1/agents/{other_agent.id}/wallet/policy",
        json={
            "max_value_per_call_atomic": 1_000_000,
            "daily_budget_atomic": 50_000_000,
            "allowed_contracts": [],
            "allow_erc8183": False,
        },
    )
    assert res_put.status_code == 404

    res_bal = await api.get(f"/api/v1/agents/{other_agent.id}/wallet/balances")
    assert res_bal.status_code == 404

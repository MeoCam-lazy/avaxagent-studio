"""Regression tests for ERC-8004 URI refresh endpoint and worker."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_wallet
from tests.fakes import FakeQueue

from app.control_plane.agents.models import AgentStatus
from app.core.queue import REFRESH_AGENT_URI, get_queue
from app.data_plane.workers.tasks import refresh_agent_uri
from app.main import app


class _StubERC8004:
    def __init__(self, success: bool = True, tx_hash: str = "0xcd34") -> None:
        self.success = success
        self.tx_hash = tx_hash
        self.uri_updates: list[tuple[int, str]] = []

    def set_agent_uri(self, agent_id: int, uri: str) -> dict:
        self.uri_updates.append((agent_id, uri))
        if not self.success:
            return {"success": False, "error": "setAgentURI reverted"}
        return {"success": True, "transactionHash": self.tx_hash, "agentURI": uri}


@pytest.fixture
def fake_queue():
    q = FakeQueue()
    app.dependency_overrides[get_queue] = lambda: q
    yield q
    app.dependency_overrides.pop(get_queue, None)


@pytest.mark.asyncio
async def test_refresh_uri_enqueues_refresh_task(
    api: httpx.AsyncClient, db: AsyncSession, fake_queue: FakeQueue
):
    unreg = await make_agent(db, status=AgentStatus.PROVISIONING, slug="unreg-refresh")
    res_400 = await api.post(f"/api/v1/agents/{unreg.id}/registration/refresh-uri")
    assert res_400.status_code == 400

    no_wallet = await make_agent(
        db, status=AgentStatus.ACTIVE, erc8004_agent_id=76, slug="nowallet-refresh"
    )
    res_409 = await api.post(f"/api/v1/agents/{no_wallet.id}/registration/refresh-uri")
    assert res_409.status_code == 409

    wallet = await make_wallet(db, address="0x" + "ab" * 20)
    reg = await make_agent(
        db,
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        erc8004_agent_id=77,
        slug="reg-refresh",
    )
    await db.flush()

    res_ok = await api.post(f"/api/v1/agents/{reg.id}/registration/refresh-uri")
    assert res_ok.status_code == 200
    assert res_ok.json()["state"] == "registered"
    assert len(fake_queue.enqueued) == 1
    fn, args, _ = fake_queue.enqueued[0]
    assert fn == REFRESH_AGENT_URI
    assert args[0] == str(reg.id)


@pytest.mark.asyncio
async def test_refresh_agent_uri_updates_onchain_and_db(db: AsyncSession, monkeypatch):
    stub = _StubERC8004(tx_hash="0xcd34")
    mock_signer = MagicMock(address="0x000000000000000000000000000000000000dead")
    monkeypatch.setattr("app.data_plane.workers.tasks.erc8004_agent", lambda wallet: stub)
    monkeypatch.setattr("app.data_plane.workers.tasks.agent_signer", lambda wallet: mock_signer)

    wallet = await make_wallet(db)
    agent = await make_agent(
        db,
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        erc8004_agent_id=77,
        agent_uri="data:old",
        name="Updated Agent Profile",
    )
    await db.commit()

    await refresh_agent_uri({"session": db}, str(agent.id))

    await db.refresh(agent)
    assert len(stub.uri_updates) == 1
    called_id, called_uri = stub.uri_updates[0]
    assert called_id == 77
    assert called_uri.startswith("data:application/json;base64,")
    assert agent.agent_uri == called_uri

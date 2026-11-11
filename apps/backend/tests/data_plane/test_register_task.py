from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_wallet

from app.control_plane.agents.models import AgentStatus
from app.data_plane.workers.tasks import register_agent


class StubERC8004Client:
    def __init__(self, success: bool = True, agent_id: int = 42, tx_hash: str = "0xab12"):
        self.success = success
        self.agent_id = agent_id
        self.tx_hash = tx_hash
        self.calls: list[str] = []

    def register_agent(self, uri: str) -> dict:
        self.calls.append(uri)
        if not self.success:
            return {"success": False, "error": "tx reverted"}
        return {
            "success": True,
            "agentId": self.agent_id,
            "transactionHash": self.tx_hash,
        }


@pytest.mark.asyncio
async def test_task_stores_agent_id(db: AsyncSession, monkeypatch):
    stub = StubERC8004Client()
    mock_signer = MagicMock(address="0x000000000000000000000000000000000000dead")
    monkeypatch.setattr("app.data_plane.workers.tasks.erc8004_agent", lambda wallet: stub)
    monkeypatch.setattr("app.data_plane.workers.tasks.agent_signer", lambda wallet: mock_signer)

    agent = await make_agent(db, status=AgentStatus.REGISTERING)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.commit()

    ctx = {"session": db}
    await register_agent(ctx, str(agent.id))

    await db.refresh(agent)
    assert agent.status == AgentStatus.ACTIVE
    assert agent.erc8004_agent_id == 42
    assert agent.registration_tx_hash == "0xab12"
    assert len(stub.calls) == 1


@pytest.mark.asyncio
async def test_task_idempotent_when_registered(db: AsyncSession, monkeypatch):
    stub = StubERC8004Client()
    mock_signer = MagicMock(address="0x000000000000000000000000000000000000dead")
    monkeypatch.setattr("app.data_plane.workers.tasks.erc8004_agent", lambda wallet: stub)
    monkeypatch.setattr("app.data_plane.workers.tasks.agent_signer", lambda wallet: mock_signer)

    agent = await make_agent(db, status=AgentStatus.ACTIVE)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    agent.erc8004_agent_id = 99
    await db.commit()

    ctx = {"session": db}
    await register_agent(ctx, str(agent.id))

    assert len(stub.calls) == 0


@pytest.mark.asyncio
async def test_task_failure_reverts_status(db: AsyncSession, monkeypatch):
    stub = StubERC8004Client(success=False)
    mock_signer = MagicMock(address="0x000000000000000000000000000000000000dead")
    monkeypatch.setattr("app.data_plane.workers.tasks.erc8004_agent", lambda wallet: stub)
    monkeypatch.setattr("app.data_plane.workers.tasks.agent_signer", lambda wallet: mock_signer)

    agent = await make_agent(db, status=AgentStatus.REGISTERING)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.commit()

    ctx = {"session": db}
    with pytest.raises(RuntimeError):
        await register_agent(ctx, str(agent.id))

    await db.refresh(agent)
    assert agent.status == AgentStatus.FAILED


@pytest.mark.asyncio
async def test_production_failure_is_persisted_and_reported(api, db: AsyncSession, monkeypatch):
    """The arq worker passes no session: the failure must survive the raise."""
    from tests.conftest import TestSessionLocal

    stub = StubERC8004Client(success=False)
    mock_signer = MagicMock(address="0x000000000000000000000000000000000000dead")
    monkeypatch.setattr("app.data_plane.workers.tasks.erc8004_agent", lambda wallet: stub)
    monkeypatch.setattr("app.data_plane.workers.tasks.agent_signer", lambda wallet: mock_signer)
    monkeypatch.setattr("app.data_plane.workers.tasks.SessionLocal", TestSessionLocal)

    agent = await make_agent(db, status=AgentStatus.REGISTERING)
    wallet = await make_wallet(db)
    agent.wallet_id = wallet.id
    await db.commit()

    agent_id = agent.id
    with pytest.raises(RuntimeError):
        await register_agent({}, str(agent_id))

    db.expire_all()  # the api fixture shares this session; drop its cached agent
    res = await api.get(f"/api/v1/agents/{agent_id}/registration")
    assert res.status_code == 200
    assert res.json()["state"] == "failed"

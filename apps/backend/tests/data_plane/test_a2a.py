from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from eth_account import Account
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal
from tests.data_plane.test_x402_verify import _make_signed_payment
from tests.factories import make_agent, make_job, make_wallet
from tests.fakes import FakeChainReader, FakeQueue, FakeRelayer

from app.chain.network import payment_asset_address
from app.chain.reader import get_chain_reader
from app.control_plane.agents.models import AgentStatus
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.jobs.models import Job, JobEvent, JobStatus
from app.core.config import SettlementMode
from app.core.queue import get_queue
from app.data_plane.gateway.main import app as gateway_app
from app.data_plane.gateway.relayer import get_relayer
from app.db.session import get_session


@pytest_asyncio.fixture
async def gateway_context(db: AsyncSession):
    fake_relayer = FakeRelayer()
    fake_reader = FakeChainReader()
    fake_queue = FakeQueue()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield db

    gateway_app.dependency_overrides[get_session] = _override_session
    gateway_app.dependency_overrides[get_relayer] = lambda: fake_relayer
    gateway_app.dependency_overrides[get_chain_reader] = lambda: fake_reader
    gateway_app.dependency_overrides[get_queue] = lambda: fake_queue

    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, fake_relayer, fake_reader, fake_queue

    gateway_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_no_payment_returns_402(gateway_context, db: AsyncSession):
    client, _, _, _ = gateway_context
    agent = await make_agent(db, status=AgentStatus.ACTIVE, price_atomic=2_000_000)
    wallet = await make_wallet(db, address="0x" + "11" * 20)
    agent.wallet_id = wallet.id
    await db.commit()

    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": "hello"},
    }
    res = await client.post(f"/agents/{agent.slug}/a2a", json=req)
    assert res.status_code == 402
    body = res.json()
    assert body["x402Version"] == 1
    assert body["error"] == "payment_required"
    assert len(body["accepts"]) == 1
    accept = body["accepts"][0]
    assert accept["amount"] == "2000000"
    assert accept["payTo"].lower() == wallet.address.lower()
    assert accept["asset"].lower() == payment_asset_address().lower()


@pytest.mark.asyncio
async def test_paid_call_creates_funded_job_and_enqueues(gateway_context, db: AsyncSession):
    client, fake_relayer, _, fake_queue = gateway_context
    agent = await make_agent(db, status=AgentStatus.ACTIVE, price_atomic=2_000_000)
    wallet = await make_wallet(db, address="0x" + "11" * 20)
    agent.wallet_id = wallet.id
    await db.commit()

    signer = Account.create()
    now = int(time.time())
    _, encoded_payment = _make_signed_payment(
        signer,
        to=wallet.address,
        value=2_000_000,
        valid_after=now - 60,
        valid_before=now + 300,
    )

    req = {
        "jsonrpc": "2.0",
        "id": "msg-1",
        "method": "message/send",
        "params": {"message": "analyze avax data"},
    }
    res = await client.post(
        f"/agents/{agent.slug}/a2a",
        json=req,
        headers={"X-PAYMENT": encoded_payment},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "msg-1"
    result = body["result"]
    assert result["kind"] == "task"
    assert result["status"]["state"] == "submitted"

    job_id = result["id"]
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    assert job is not None
    assert job.status == JobStatus.FUNDED
    assert job.amount_atomic == 2_000_000
    assert job.payment_tx_hash == fake_relayer.tx_hash
    assert job.client_address.lower() == signer.address.lower()

    # Verify ledger entries
    ledger_rows = (
        (await db.execute(select(LedgerEntry).where(LedgerEntry.job_id == job.id))).scalars().all()
    )
    assert len(ledger_rows) == 2
    kinds = {row.kind for row in ledger_rows}
    assert kinds == {LedgerKind.INCOME, LedgerKind.STUDIO_FEE}

    # Verify job events
    events = (await db.execute(select(JobEvent).where(JobEvent.job_id == job.id))).scalars().all()
    assert any(e.type == "funded" for e in events)

    # Verify enqueued job runner
    assert len(fake_queue.enqueued) == 1
    assert fake_queue.enqueued[0][0] == "run_job"
    assert fake_queue.enqueued[0][1] == (str(job.id),)


@pytest.mark.asyncio
async def test_replayed_authorization_rejected(gateway_context, db: AsyncSession):
    client, fake_relayer, _, _ = gateway_context
    agent = await make_agent(db, status=AgentStatus.ACTIVE, price_atomic=1_000_000)
    agent_id = agent.id
    agent_slug = agent.slug
    wallet = await make_wallet(db, address="0x" + "22" * 20)
    agent.wallet_id = wallet.id
    await db.commit()

    signer = Account.create()
    now = int(time.time())
    _, encoded_payment = _make_signed_payment(
        signer,
        to=wallet.address,
        value=1_000_000,
        valid_after=now - 60,
        valid_before=now + 300,
    )

    req = {"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {}}
    res1 = await client.post(
        f"/agents/{agent_slug}/a2a",
        json=req,
        headers={"X-PAYMENT": encoded_payment},
    )
    assert res1.status_code == 200

    # Second request with same authorization
    res2 = await client.post(
        f"/agents/{agent_slug}/a2a",
        json=req,
        headers={"X-PAYMENT": encoded_payment},
    )
    assert res2.status_code == 409
    assert res2.json()["error"] == "payment_replayed"

    # Verify only one job created and one settle call
    jobs = (await db.execute(select(Job).where(Job.agent_id == agent_id))).scalars().all()
    assert len(jobs) == 1
    assert len(fake_relayer.calls) == 1


@pytest.mark.asyncio
async def test_concurrent_same_nonce_single_job(db: AsyncSession):
    # Concurrency test must run with independent sessions from TestSessionLocal
    fake_relayer = FakeRelayer()
    fake_reader = FakeChainReader()
    fake_queue = FakeQueue()

    agent = await make_agent(db, status=AgentStatus.ACTIVE, price_atomic=1_000_000)
    wallet = await make_wallet(db, address="0x" + "33" * 20)
    agent.wallet_id = wallet.id
    await db.commit()

    agent_id = agent.id
    agent_slug = agent.slug

    signer = Account.create()
    now = int(time.time())
    _, encoded_payment = _make_signed_payment(
        signer,
        to=wallet.address,
        value=1_000_000,
        valid_after=now - 60,
        valid_before=now + 300,
    )

    async def _independent_session() -> AsyncIterator[AsyncSession]:
        async with TestSessionLocal() as session:
            yield session

    from app.db.session import get_session

    gateway_app.dependency_overrides[get_session] = _independent_session
    gateway_app.dependency_overrides[get_relayer] = lambda: fake_relayer
    gateway_app.dependency_overrides[get_chain_reader] = lambda: fake_reader
    gateway_app.dependency_overrides[get_queue] = lambda: fake_queue

    transport = httpx.ASGITransport(app=gateway_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as c1,
        httpx.AsyncClient(transport=transport, base_url="http://test") as c2,
    ):
        r1, r2 = await asyncio.gather(
            c1.post(
                f"/agents/{agent_slug}/a2a",
                json={"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {}},
                headers={"X-PAYMENT": encoded_payment},
            ),
            c2.post(
                f"/agents/{agent_slug}/a2a",
                json={"jsonrpc": "2.0", "id": 2, "method": "message/send", "params": {}},
                headers={"X-PAYMENT": encoded_payment},
            ),
        )

    statuses = {r1.status_code, r2.status_code}
    assert statuses == {200, 409}
    assert len(fake_relayer.calls) == 1

    jobs = (await db.execute(select(Job).where(Job.agent_id == agent_id))).scalars().all()
    assert len(jobs) == 1
    gateway_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_relayer_failure_marks_failed_no_income(gateway_context, db: AsyncSession):
    client, fake_relayer, _, _ = gateway_context
    fake_relayer.should_fail = True

    agent = await make_agent(db, status=AgentStatus.ACTIVE, price_atomic=1_000_000)
    wallet = await make_wallet(db, address="0x" + "44" * 20)
    agent.wallet_id = wallet.id
    await db.commit()

    signer = Account.create()
    now = int(time.time())
    _, encoded_payment = _make_signed_payment(
        signer,
        to=wallet.address,
        value=1_000_000,
        valid_after=now - 60,
        valid_before=now + 300,
    )

    res = await client.post(
        f"/agents/{agent.slug}/a2a",
        json={"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {}},
        headers={"X-PAYMENT": encoded_payment},
    )
    assert res.status_code == 502
    assert res.json()["error"] == "settlement_failed"

    jobs = (await db.execute(select(Job).where(Job.agent_id == agent.id))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.FAILED

    ledger_entries = (
        (await db.execute(select(LedgerEntry).where(LedgerEntry.job_id == jobs[0].id)))
        .scalars()
        .all()
    )
    assert len(ledger_entries) == 0


@pytest.mark.asyncio
async def test_tasks_get_maps_state(gateway_context, db: AsyncSession):
    client, _, _, _ = gateway_context
    agent = await make_agent(db, status=AgentStatus.ACTIVE)

    # 1. Funded/Running -> working
    job_funded = await make_job(
        db,
        agent,
        status=JobStatus.FUNDED,
        settlement_mode=SettlementMode.X402,
    )
    res_funded = await client.post(
        f"/agents/{agent.slug}/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {"id": str(job_funded.id)},
        },
    )
    assert res_funded.status_code == 200
    assert res_funded.json()["result"]["status"]["state"] == "working"

    # 2. Submitted/Settled -> completed with artifacts
    job_completed = await make_job(
        db,
        agent,
        status=JobStatus.SUBMITTED,
        settlement_mode=SettlementMode.X402,
        deliverable_uri="http://storage/result.json",
    )
    res_completed = await client.post(
        f"/agents/{agent.slug}/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tasks/get",
            "params": {"id": str(job_completed.id)},
        },
    )
    assert res_completed.status_code == 200
    result = res_completed.json()["result"]
    assert result["status"]["state"] == "completed"
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["uri"] == "http://storage/result.json"

    # 3. Failed -> failed
    job_failed = await make_job(
        db,
        agent,
        status=JobStatus.FAILED,
        settlement_mode=SettlementMode.X402,
        error="Something went wrong",
    )
    res_failed = await client.post(
        f"/agents/{agent.slug}/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tasks/get",
            "params": {"id": str(job_failed.id)},
        },
    )
    assert res_failed.status_code == 200
    assert res_failed.json()["result"]["status"]["state"] == "failed"
    assert res_failed.json()["result"]["error"] == "Something went wrong"


@pytest.mark.asyncio
async def test_unknown_method_jsonrpc_error(gateway_context, db: AsyncSession):
    client, _, _, _ = gateway_context
    agent = await make_agent(db, status=AgentStatus.ACTIVE)

    res = await client.post(
        f"/agents/{agent.slug}/a2a",
        json={"jsonrpc": "2.0", "id": 99, "method": "custom/unknown", "params": {}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 99
    assert body["error"]["code"] == -32601

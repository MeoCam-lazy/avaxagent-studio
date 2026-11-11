"""End-to-end tests for ERC-8183 escrow across gateway, indexer, worker, and settler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from eth_abi import encode as abi_encode
from hexbytes import HexBytes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal
from tests.factories import make_agent, make_job, make_wallet
from tests.fakes import FakeQueue, FakeRelayer
from web3 import Web3

from app.chain import network as net
from app.chain.commerce import PolicyVerdict
from app.chain.reader import get_chain_reader
from app.control_plane.agents.models import AgentStatus
from app.control_plane.billing.ledger import balances
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.jobs.models import Job, JobEvent, JobStatus
from app.core.config import SettlementMode, settings
from app.core.queue import RUN_JOB, get_queue
from app.data_plane.gateway.main import app as gateway_app
from app.data_plane.gateway.relayer import get_relayer
from app.data_plane.indexer.streams import (
    ERC20_TRANSFER_EVENT_ABI,
    JOB_FUNDED_TOPIC,
    EscrowJobStream,
    IncomeStream,
)
from app.data_plane.settler.escrow import EscrowSettler
from app.data_plane.settler.service import SettleBot
from app.data_plane.workers import tasks as worker_tasks
from app.db.session import get_session

COMMERCE_ADDR = "0x1111111111111111111111111111111111111111"
ROUTER_ADDR = "0x2222222222222222222222222222222222222222"
POLICY_ADDR = "0x3333333333333333333333333333333333333333"
CLIENT_ADDR = "0x5555555555555555555555555555555555555555"


def _enable_commerce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "commerce_address", COMMERCE_ADDR)
    monkeypatch.setattr(settings, "router_address", ROUTER_ADDR)
    monkeypatch.setattr(settings, "policy_address", POLICY_ADDR)


def _addr_topic(addr: str) -> bytes:
    return bytes.fromhex("00" * 12 + addr.removeprefix("0x").lower())


def _uint_topic(val: int) -> bytes:
    return val.to_bytes(32, "big")


def _build_job_funded_log(
    *,
    job_id: int,
    client: str,
    provider: str,
    amount: int,
    tx_hash: str = "0x" + "aa" * 32,
    log_index: int = 0,
) -> dict:
    return {
        "address": Web3.to_checksum_address(COMMERCE_ADDR),
        "topics": [
            HexBytes(JOB_FUNDED_TOPIC),
            HexBytes(_uint_topic(job_id)),
            HexBytes(_addr_topic(client)),
            HexBytes(_addr_topic(provider)),
        ],
        "data": HexBytes(abi_encode(["uint256"], [amount])),
        "transactionHash": HexBytes(tx_hash),
        "blockHash": HexBytes("0x" + "99" * 32),
        "transactionIndex": 0,
        "logIndex": log_index,
        "blockNumber": 100,
    }


class StubCommerceClient:
    def __init__(
        self,
        *,
        verdict: int = int(PolicyVerdict.APPROVED),
        submit_tx: str = "0x" + "bb" * 32,
        settle_tx: str = "0x" + "cc" * 32,
        description: str = "Analyze Avalanche DEX liquidity",
    ) -> None:
        self.verdict = verdict
        self.submit_tx = submit_tx
        self.settle_tx = settle_tx
        self.description = description
        self.submitted: list[tuple[int, str, bytes]] = []
        self.settled: list[int] = []

    def get_job(self, job_id: int) -> dict:
        return {"id": job_id, "description": self.description}

    def submit_result(self, job_id: int, deliverable_uri: str, deliverable_hash: bytes) -> str:
        self.submitted.append((job_id, deliverable_uri, bytes(deliverable_hash)))
        return self.submit_tx

    def policy_verdict(self, job_id: int, evidence: bytes = b"") -> tuple[int, str]:
        return self.verdict, "0x" + "00" * 32

    def settle(self, job_id: int, evidence: bytes = b"") -> str:
        self.settled.append(job_id)
        return self.settle_tx


@pytest.mark.asyncio
async def test_disabled_raises_409(db: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commerce_address", None)
    monkeypatch.setattr(settings, "router_address", None)
    monkeypatch.setattr(settings, "policy_address", None)

    wallet = await make_wallet(db)
    agent = await make_agent(
        db,
        slug="escrow-disabled-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
    )
    await db.commit()

    async def _override_db():
        yield db

    gateway_app.dependency_overrides[get_session] = _override_db
    gateway_app.dependency_overrides[get_relayer] = lambda: FakeRelayer()
    gateway_app.dependency_overrides[get_chain_reader] = lambda: MagicMock()
    gateway_app.dependency_overrides[get_queue] = lambda: FakeQueue()
    try:
        transport = httpx.ASGITransport(app=gateway_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gw") as gw:
            res = await gw.post(
                f"/agents/{agent.slug}/a2a",
                json={"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {}},
            )
        assert res.status_code == 409
        body = res.json()
        assert body["error"] == "feature_disabled"
        assert body["feature"] == "erc8183"
    finally:
        gateway_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gateway_returns_escrow_params(db: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    wallet = await make_wallet(db, address="0x7777777777777777777777777777777777777777")
    agent = await make_agent(
        db,
        slug="escrow-live-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
        price_atomic=350_000,
    )
    await db.commit()

    async def _override_db():
        yield db

    gateway_app.dependency_overrides[get_session] = _override_db
    gateway_app.dependency_overrides[get_relayer] = lambda: FakeRelayer()
    gateway_app.dependency_overrides[get_chain_reader] = lambda: MagicMock()
    gateway_app.dependency_overrides[get_queue] = lambda: FakeQueue()
    try:
        transport = httpx.ASGITransport(app=gateway_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gw") as gw:
            card_res = await gw.get(f"/agents/{agent.slug}/.well-known/agent-card.json")
            assert card_res.status_code == 200
            ext = card_res.json()["extensions"]["erc8183"]
            assert ext["commerce"] == COMMERCE_ADDR
            assert ext["provider"] == wallet.address

            res = await gw.post(
                f"/agents/{agent.slug}/a2a",
                json={"jsonrpc": "2.0", "id": 9, "method": "message/send", "params": {}},
            )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["commerce"] == COMMERCE_ADDR
        assert result["router"] == ROUTER_ADDR
        assert result["policy"] == POLICY_ADDR
        assert result["provider"] == wallet.address
        assert result["price"] == "350000"
        assert result["token"] == net.payment_asset_address()
    finally:
        gateway_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jobfunded_creates_job_once(db: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    wallet = await make_wallet(db, address="0x8888888888888888888888888888888888888888")
    agent = await make_agent(
        db,
        slug="indexed-escrow-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
    )
    await db.commit()

    fake_q = FakeQueue()
    stub_reader = StubCommerceClient(description="Audit StakingPool.sol")
    stream = EscrowJobStream(queue=fake_q, commerce_reader=stub_reader)

    managed_log = _build_job_funded_log(
        job_id=42,
        client=CLIENT_ADDR,
        provider=wallet.address,
        amount=250_000,
    )
    stranger_log = _build_job_funded_log(
        job_id=43,
        client=CLIENT_ADDR,
        provider="0x9999999999999999999999999999999999999999",
        amount=250_000,
    )

    await stream.handle(db, [managed_log, stranger_log])
    await db.commit()

    # Re-delivering the exact same log must be idempotent on (chain_id, chain_job_id)
    await stream.handle(db, [managed_log])
    await db.commit()

    jobs = (await db.execute(select(Job).where(Job.agent_id == agent.id))).scalars().all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.settlement_mode == SettlementMode.ERC8183
    assert job.status == JobStatus.FUNDED
    assert job.chain_job_id == 42
    assert job.amount_atomic == 250_000
    assert job.request["message"] == "Audit StakingPool.sol"

    assert len(fake_q.enqueued) == 1
    fn_name, args, _ = fake_q.enqueued[0]
    assert fn_name == RUN_JOB
    assert args == (str(job.id),)


class _FakeLlmRunner:
    def __init__(self, response: str) -> None:
        self.response = response

    async def complete(self, *, model: str, system: str, prompt: str, temperature: float) -> str:
        return self.response


@pytest.mark.asyncio
async def test_worker_submits_for_erc8183(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    from avaxagent.storage import LocalStorageProvider

    _enable_commerce(monkeypatch)
    stub = StubCommerceClient(submit_tx="0x" + "dd" * 32)
    storage = LocalStorageProvider(base_dir=str(tmp_path))

    monkeypatch.setattr(worker_tasks, "get_llm_runner", lambda: _FakeLlmRunner("Audit clean"))
    monkeypatch.setattr(worker_tasks, "get_storage", lambda: storage)
    monkeypatch.setattr(worker_tasks, "agent_signer", lambda w: MagicMock(address=w.address))
    monkeypatch.setattr(worker_tasks, "erc8183_client", lambda _signer: stub)
    monkeypatch.setattr(worker_tasks, "SessionLocal", TestSessionLocal)

    wallet = await make_wallet(db, address="0x6666666666666666666666666666666666666666")
    agent = await make_agent(
        db,
        slug="worker-escrow-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
    )
    job = await make_job(
        db,
        agent,
        settlement_mode=SettlementMode.ERC8183,
        status=JobStatus.FUNDED,
        chain_job_id=77,
        request={"message": "Check access controls"},
    )
    job_id = job.id
    await db.commit()

    await worker_tasks.run_job({}, str(job_id))

    db.expire_all()
    refreshed = await db.get(Job, job_id)
    assert refreshed is not None
    assert refreshed.status == JobStatus.SUBMITTED
    assert refreshed.submit_tx_hash == "0x" + "dd" * 32
    assert refreshed.deliverable_uri is not None
    assert len(stub.submitted) == 1
    assert stub.submitted[0][0] == 77


@pytest.mark.asyncio
async def test_settler_settles_and_books_income(db: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    stub = StubCommerceClient(
        verdict=int(PolicyVerdict.PENDING),
        settle_tx="0x" + "ee" * 32,
    )

    wallet = await make_wallet(db, address="0x1234567890123456789012345678901234567890")
    agent = await make_agent(
        db,
        slug="settler-escrow-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
    )
    job = await make_job(
        db,
        agent,
        settlement_mode=SettlementMode.ERC8183,
        status=JobStatus.SUBMITTED,
        chain_job_id=88,
        amount_atomic=1_000_000,
        asset=net.payment_asset_address(),
    )
    job_id = job.id
    agent_id = agent.id
    wallet_addr = wallet.address
    await db.commit()

    escrow_settler = EscrowSettler(
        session_factory=TestSessionLocal,
        client_factory=lambda: stub,
    )
    bot = SettleBot(
        session_factory=TestSessionLocal,
        payout_executor=MagicMock(tick=AsyncMock()),
        fee_sweeper=MagicMock(tick=AsyncMock()),
        escrow_settler=escrow_settler,
    )

    # 1. Dispute window still open -> PENDING -> does not settle yet
    await bot.tick()
    db.expire_all()
    still_sub = await db.get(Job, job_id)
    assert still_sub.status == JobStatus.SUBMITTED
    assert stub.settled == []

    # 2. Dispute window elapsed -> APPROVED -> settles and books 95/5 ledger split
    stub.verdict = int(PolicyVerdict.APPROVED)
    await bot.tick()

    db.expire_all()
    settled_job = await db.get(Job, job_id)
    assert settled_job.status == JobStatus.SETTLED
    assert settled_job.settle_tx_hash == "0x" + "ee" * 32
    assert stub.settled == [88]

    bal = await balances(db, agent_id)
    assert bal.gross_income_atomic == 1_000_000
    assert bal.studio_fees_atomic == 50_000
    assert bal.withdrawable_atomic == 950_000

    # 3. IncomeStream seeing the ERC-20 Transfer from settle_tx_hash must NOT double-book
    transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)")
    _ = ERC20_TRANSFER_EVENT_ABI
    transfer_log = {
        "address": Web3.to_checksum_address(net.payment_asset_address()),
        "topics": [
            HexBytes(transfer_topic),
            HexBytes(_addr_topic(COMMERCE_ADDR)),
            HexBytes(_addr_topic(wallet_addr)),
        ],
        "data": HexBytes(abi_encode(["uint256"], [1_000_000])),
        "transactionHash": HexBytes("0x" + "ee" * 32),
        "blockHash": HexBytes("0x" + "99" * 32),
        "transactionIndex": 0,
        "logIndex": 2,
        "blockNumber": 200,
    }
    await IncomeStream().handle(db, [transfer_log])
    await db.commit()

    entries = (
        (await db.execute(select(LedgerEntry).where(LedgerEntry.agent_id == agent_id)))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    kinds = {e.kind for e in entries}
    assert kinds == {LedgerKind.INCOME, LedgerKind.STUDIO_FEE}


@pytest.mark.asyncio
async def test_settler_marks_refunded_when_policy_rejects(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _enable_commerce(monkeypatch)
    stub = StubCommerceClient(
        verdict=int(PolicyVerdict.REJECTED),
        settle_tx="0x" + "ff" * 32,
    )

    wallet = await make_wallet(db, address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd")
    agent = await make_agent(
        db,
        slug="rejected-escrow-agent",
        status=AgentStatus.ACTIVE,
        wallet_id=wallet.id,
        settlement_mode=SettlementMode.ERC8183,
    )
    job = await make_job(
        db,
        agent,
        settlement_mode=SettlementMode.ERC8183,
        status=JobStatus.SUBMITTED,
        chain_job_id=89,
        amount_atomic=500_000,
        asset=net.payment_asset_address(),
    )
    job_id = job.id
    agent_id = agent.id
    await db.commit()

    settler = EscrowSettler(session_factory=TestSessionLocal, client_factory=lambda: stub)
    count = await settler.tick()
    assert count == 1

    db.expire_all()
    refunded_job = await db.get(Job, job_id)
    assert refunded_job.status == JobStatus.REFUNDED
    assert refunded_job.settle_tx_hash == "0x" + "ff" * 32

    events = (await db.execute(select(JobEvent).where(JobEvent.job_id == job_id))).scalars().all()
    assert any(e.type == "refunded" for e in events)

    bal = await balances(db, agent_id)
    assert bal.gross_income_atomic == 0
    assert bal.withdrawable_atomic == 0

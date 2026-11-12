"""The plan's definition of done, end to end on Fuji (or a Fuji fork).

creator SIWE login -> create agent -> provision wallet -> ERC-8004 register
-> paid x402 call (relayed on-chain) -> worker settles the job -> earnings net
of the studio fee -> withdrawal on-chain -> fee swept to the treasury.

Only custody is swapped: the agent wallet and the relayer sign with local test
keys instead of Turnkey (see ``conftest.py``). Every chain read and write is
real. Each step asserts on-chain state, not just API answers.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from avaxagent.signing import SigningPolicy
from avaxagent.storage import LocalStorageProvider
from avaxagent.wallets import EVMWalletProvider
from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

import app.data_plane.workers.tasks as worker
from app.chain import network as net
from app.chain.reader import get_chain_reader
from app.control_plane.billing.models import PayoutStatus
from app.control_plane.wallets.turnkey_admin import SubOrg, get_turnkey_admin
from app.core.config import settings
from app.core.queue import get_queue
from app.data_plane.gateway.main import app as gateway_app
from app.data_plane.gateway.relayer import TurnkeyRelayer, get_relayer
from app.data_plane.settler.fees import FeeSweeper
from app.data_plane.settler.payouts import PayoutExecutor
from app.db.session import get_session
from app.main import app as api_app
from tests.conftest import TestSessionLocal
from tests.fuji.conftest import OWNER_OF_ABI, FujiAccounts, sign_authorization
from tests.test_auth import make_siwe_message

PRICE_ATOMIC = 100_000  # 0.1 USDC per call keeps a live run cheap


def _local_provider(account) -> EVMWalletProvider:
    """Stand-in for a Turnkey wallet: same address, key held locally."""
    return EVMWalletProvider(
        password=uuid.uuid4().hex,
        private_key=account.key.to_0x_hex(),
        persist=False,
        signing_policy=SigningPolicy.permissive(),
    )


class LocalTurnkeyAdmin:
    """Provisioning hands out the agent test key's address as the "sub-org" wallet."""

    def __init__(self, address: str) -> None:
        self.address = address

    async def create_agent_sub_org(self, name: str) -> SubOrg:
        return SubOrg(sub_org_id="local-e2e", wallet_id="local-e2e", address=self.address)

    async def set_policy(self, *args: Any, **kwargs: Any) -> None:
        return None


class CapturingQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((function, args))

    def take(self, function: str) -> str:
        for i, (fn, args) in enumerate(self.jobs):
            if fn == function:
                del self.jobs[i]
                return args[0]
        raise AssertionError(f"{function} was not enqueued: {self.jobs}")


class FakeLlm:
    async def complete(self, *, model: str, system: str, prompt: str, temperature: float) -> str:
        return f"echo: {prompt}"


async def _session() -> AsyncIterator[AsyncSession]:
    # One session per request, committed by the services, as in production.
    async with TestSessionLocal() as s:
        yield s


async def _run_task(task, job_arg: str) -> None:
    async with TestSessionLocal() as s:
        try:
            await task({"session": s}, job_arg)
        finally:
            await s.commit()


@pytest.fixture
async def stack(db, accounts: FujiAccounts, monkeypatch, tmp_path):
    """API + gateway apps in-process, wired to the chain with local custody."""
    queue = CapturingQueue()
    relayer = TurnkeyRelayer(wallet_provider=_local_provider(accounts.relayer))
    agent_wallet = _local_provider(accounts.agent)
    storage = LocalStorageProvider(base_dir=str(tmp_path))

    monkeypatch.setattr(worker, "agent_signer", lambda wallet: agent_wallet)
    monkeypatch.setattr("app.data_plane.settler.transfers.agent_signer", lambda w: agent_wallet)
    monkeypatch.setattr(worker, "get_llm_runner", lambda: FakeLlm())
    monkeypatch.setattr(worker, "get_storage", lambda: storage)
    monkeypatch.setattr("app.data_plane.gateway.a2a.get_storage", lambda: storage)

    overrides = {
        get_session: _session,
        get_queue: lambda: queue,
        get_turnkey_admin: lambda: LocalTurnkeyAdmin(accounts.agent.address),
        get_relayer: lambda: relayer,
        get_chain_reader: get_chain_reader,
    }
    api_app.dependency_overrides.update(overrides)
    gateway_app.dependency_overrides.update(overrides)
    api = httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://api")
    gateway = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gateway_app), base_url="http://gateway"
    )
    try:
        yield api, gateway, queue
    finally:
        await api.aclose()
        await gateway.aclose()
        api_app.dependency_overrides.clear()
        gateway_app.dependency_overrides.clear()


async def test_creator_to_paid_call_to_payout_on_fuji(
    stack, accounts: FujiAccounts, usdc, w3: Web3, wait_receipt, monkeypatch
):
    api, gateway, queue = stack
    asset = usdc.address
    treasury = Account.create().address
    destination = Account.create().address
    monkeypatch.setattr(settings, "studio_treasury_address", treasury)
    monkeypatch.setattr(settings, "fee_sweep_min_atomic", 1)

    # 1. Creator signs in with a wallet (SIWE).
    creator = Account.create()
    nonce = (await api.post("/api/v1/auth/nonce")).json()["nonce"]
    message = make_siwe_message(creator.address, nonce)
    signature = creator.sign_message(encode_defunct(text=message)).signature.hex()
    login = await api.post(
        "/api/v1/auth/verify", json={"message": message, "signature": signature}
    )
    assert login.status_code == 200, login.text
    api.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    # 2. Create a public x402 agent.
    slug = f"e2e-{uuid.uuid4().hex[:8]}"
    created = await api.post(
        "/api/v1/agents",
        json={
            "slug": slug,
            "name": "Fuji E2E agent",
            "description": "Echo agent used by the Fuji end-to-end suite.",
            "skills": ["e2e"],
            "settlement_mode": "x402",
            "price_atomic": PRICE_ATOMIC,
            "is_public": True,
        },
    )
    assert created.status_code == 201, created.text
    agent_id = created.json()["id"]

    # 3. Provision its wallet.
    wallet = await api.post(f"/api/v1/agents/{agent_id}/wallet")
    assert wallet.status_code == 201, wallet.text
    assert wallet.json()["address"] == accounts.agent.address

    # 4. Register on ERC-8004: the worker sends the real register tx.
    reg = await api.post(f"/api/v1/agents/{agent_id}/registration", json={})
    assert reg.status_code == 202, reg.text
    await _run_task(worker.register_agent, queue.take("register_agent"))
    status = (await api.get(f"/api/v1/agents/{agent_id}/registration")).json()
    assert status["state"] == "registered", status
    token_id = status["erc8004_agent_id"]
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(net.identity_registry()), abi=OWNER_OF_ABI
    )
    assert registry.functions.ownerOf(token_id).call() == accounts.agent.address
    assert wait_receipt(status["tx_hash"])["status"] == 1

    # The agent is now listed in the marketplace.
    profile = await api.get(f"/api/v1/marketplace/agents/{slug}")
    assert profile.status_code == 200, profile.text

    # 5. A client pays per call over x402; the relayer settles on-chain.
    agent_usdc_before = usdc.functions.balanceOf(accounts.agent.address).call()
    payer_usdc_before = usdc.functions.balanceOf(accounts.payer.address).call()
    payer_avax_before = w3.eth.get_balance(accounts.payer.address)

    rpc = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "ping"}]}},
    }
    quote = await gateway.post(f"/agents/{slug}/a2a", json=rpc)
    assert quote.status_code == 402, quote.text
    accept = quote.json()["accepts"][0]
    assert accept["payTo"] == accounts.agent.address and accept["amount"] == str(PRICE_ATOMIC)

    signed = sign_authorization(accounts.payer, accept, now=int(time.time()))
    envelope = {
        "x402Version": 1,
        "scheme": "exact",
        "network": accept["network"],
        "payload": signed,
    }
    x_payment = base64.b64encode(json.dumps(envelope).encode()).decode()
    paid = await gateway.post(f"/agents/{slug}/a2a", json=rpc, headers={"X-PAYMENT": x_payment})
    assert paid.status_code == 200, paid.text
    receipt = json.loads(base64.b64decode(paid.headers["X-PAYMENT-RESPONSE"]))
    assert wait_receipt(receipt["transaction"])["status"] == 1
    assert usdc.functions.balanceOf(accounts.agent.address).call() == (
        agent_usdc_before + PRICE_ATOMIC
    )
    assert usdc.functions.balanceOf(accounts.payer.address).call() == (
        payer_usdc_before - PRICE_ATOMIC
    )
    # Gasless for the payer: the relayer paid the AVAX.
    assert w3.eth.get_balance(accounts.payer.address) == payer_avax_before

    # The same signed payment cannot be spent twice.
    replay = await gateway.post(f"/agents/{slug}/a2a", json=rpc, headers={"X-PAYMENT": x_payment})
    assert replay.status_code == 409, replay.text

    # 6. The worker runs the job; the payer reads the output over A2A.
    task_id = paid.json()["result"]["id"]
    await _run_task(worker.run_job, queue.take("run_job"))
    task = await gateway.post(
        f"/agents/{slug}/a2a",
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": task_id}},
    )
    result = task.json()["result"]
    assert result["status"]["state"] == "completed", result
    assert result["artifacts"][0]["parts"][0]["text"] == "echo: ping"
    job = (await api.get(f"/api/v1/jobs/{task_id}")).json()
    assert job["status"] == "settled" and job["payment_tx_hash"] == receipt["transaction"]

    # 7. Earnings are booked net of the studio fee.
    fee = PRICE_ATOMIC * settings.studio_fee_bps // 10_000
    summary = (await api.get("/api/v1/billing/summary")).json()
    assert summary["gross_income_atomic"] == PRICE_ATOMIC
    assert summary["studio_fees_atomic"] == fee
    assert summary["withdrawable_atomic"] == PRICE_ATOMIC - fee

    # 8. Withdraw to an external address; the settler sends it on-chain.
    payout = await api.post(
        "/api/v1/billing/payouts",
        json={
            "agent_id": agent_id,
            "destination": destination,
            "amount_atomic": PRICE_ATOMIC - fee,
        },
    )
    assert payout.status_code == 202, payout.text
    await PayoutExecutor(session_factory=TestSessionLocal).tick()
    payouts = (await api.get("/api/v1/billing/payouts")).json()
    assert payouts[0]["status"] == PayoutStatus.CONFIRMED.value, payouts
    assert wait_receipt(payouts[0]["tx_hash"])["status"] == 1
    assert usdc.functions.balanceOf(destination).call() == PRICE_ATOMIC - fee
    assert (await api.get("/api/v1/billing/summary")).json()["withdrawable_atomic"] == 0

    # 9. The studio fee is swept to the treasury.
    await FeeSweeper(session_factory=TestSessionLocal).tick()
    assert usdc.functions.balanceOf(treasury).call() == fee
    assert usdc.functions.balanceOf(accounts.agent.address).call() == agent_usdc_before
    assert asset == Web3.to_checksum_address(net.payment_asset_address())

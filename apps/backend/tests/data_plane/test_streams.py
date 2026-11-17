from __future__ import annotations

from typing import Any

import pytest
from hexbytes import HexBytes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.ledger import record_income
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.wallets.models import Wallet
from app.data_plane.indexer.streams import (
    ERC20_TRANSFER_EVENT_ABI,
    IDENTITY_REGISTRY_EVENTS_ABI,
    IdentityStream,
    IncomeStream,
)

w3 = Web3()
id_contract = w3.eth.contract(abi=IDENTITY_REGISTRY_EVENTS_ABI)
erc20_contract = w3.eth.contract(abi=ERC20_TRANSFER_EVENT_ABI)


def make_registered_log(
    agent_id: int,
    agent_uri: str,
    owner: str,
    tx_hash: str = "0x" + "aa" * 32,
    log_index: int = 0,
) -> dict[str, Any]:
    event = id_contract.events.Registered()
    topic0 = event.build_filter().topics[0]
    topic1 = "0x" + (agent_id).to_bytes(32, "big").hex()
    clean_owner = owner[2:] if owner.startswith("0x") else owner
    topic2 = "0x" + bytes.fromhex(clean_owner).rjust(32, b"\x00").hex()
    data = w3.codec.encode(["string"], [agent_uri]).hex()
    return {
        "address": "0x5555555555555555555555555555555555555555",
        "topics": [HexBytes(topic0), HexBytes(topic1), HexBytes(topic2)],
        "data": HexBytes(data),
        "blockNumber": 100,
        "blockHash": HexBytes("0x" + "99" * 32),
        "transactionHash": HexBytes(tx_hash),
        "logIndex": log_index,
        "transactionIndex": 0,
    }


def make_transfer_identity_log(
    from_addr: str,
    to_addr: str,
    token_id: int,
    tx_hash: str = "0x" + "bb" * 32,
    log_index: int = 0,
) -> dict[str, Any]:
    event = id_contract.events.Transfer()
    topic0 = event.build_filter().topics[0]
    clean_from = from_addr[2:] if from_addr.startswith("0x") else from_addr
    clean_to = to_addr[2:] if to_addr.startswith("0x") else to_addr
    topic1 = "0x" + bytes.fromhex(clean_from).rjust(32, b"\x00").hex()
    topic2 = "0x" + bytes.fromhex(clean_to).rjust(32, b"\x00").hex()
    topic3 = "0x" + (token_id).to_bytes(32, "big").hex()
    return {
        "address": "0x5555555555555555555555555555555555555555",
        "topics": [HexBytes(topic0), HexBytes(topic1), HexBytes(topic2), HexBytes(topic3)],
        "data": HexBytes("0x"),
        "blockNumber": 101,
        "blockHash": HexBytes("0x" + "99" * 32),
        "transactionHash": HexBytes(tx_hash),
        "logIndex": log_index,
        "transactionIndex": 0,
    }


def make_erc20_transfer_log(
    from_addr: str,
    to_addr: str,
    value: int,
    tx_hash: str = "0x" + "cc" * 32,
    log_index: int = 0,
) -> dict[str, Any]:
    event = erc20_contract.events.Transfer()
    topic0 = event.build_filter().topics[0]
    clean_from = from_addr[2:] if from_addr.startswith("0x") else from_addr
    clean_to = to_addr[2:] if to_addr.startswith("0x") else to_addr
    topic1 = "0x" + bytes.fromhex(clean_from).rjust(32, b"\x00").hex()
    topic2 = "0x" + bytes.fromhex(clean_to).rjust(32, b"\x00").hex()
    data = "0x" + (value).to_bytes(32, "big").hex()
    return {
        "address": "0x5425890298aed601595a70AB815c96711a31Bc65",
        "topics": [HexBytes(topic0), HexBytes(topic1), HexBytes(topic2)],
        "data": HexBytes(data),
        "blockNumber": 102,
        "blockHash": HexBytes("0x" + "99" * 32),
        "transactionHash": HexBytes(tx_hash),
        "logIndex": log_index,
        "transactionIndex": 0,
    }


@pytest.mark.asyncio
async def test_registered_event_confirms_agent(db: AsyncSession):
    wallet = Wallet(address="0x" + "11" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-1",
        slug="agent-reg",
        name="Agent Register",
        status=AgentStatus.REGISTERING,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.commit()

    stream = IdentityStream()
    log = make_registered_log(
        agent_id=42,
        agent_uri="https://studio.test/agent/card.json",
        owner=wallet.address,
    )

    await stream.handle(db, [log])
    await db.commit()

    updated = await db.get(Agent, agent.id)
    assert updated.erc8004_agent_id == 42
    assert updated.agent_uri == "https://studio.test/agent/card.json"
    assert updated.status == AgentStatus.ACTIVE


@pytest.mark.asyncio
async def test_identity_transfer_pauses_agent(db: AsyncSession):
    wallet = Wallet(address="0x" + "22" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-2",
        slug="agent-pause",
        name="Agent Pause",
        status=AgentStatus.ACTIVE,
        erc8004_agent_id=77,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.commit()

    stream = IdentityStream()
    log = make_transfer_identity_log(
        from_addr=wallet.address,
        to_addr="0x" + "99" * 20,
        token_id=77,
    )

    await stream.handle(db, [log])
    await db.commit()

    updated = await db.get(Agent, agent.id)
    assert updated.status == AgentStatus.PAUSED


@pytest.mark.asyncio
async def test_income_matches_job_payment(db: AsyncSession):
    wallet = Wallet(address="0x" + "33" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-3",
        slug="agent-income-job",
        name="Agent Income Job",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.flush()

    tx_hash = "0x" + "33" * 32
    job = Job(
        agent_id=agent.id,
        settlement_mode=agent.settlement_mode,
        client_address="0x" + "44" * 20,
        chain_id=43113,
        status=JobStatus.SUBMITTED,
        amount_atomic=1_000_000,
        asset="USDC",
        payment_tx_hash=tx_hash,
    )
    db.add(job)
    await db.flush()

    # Pre-book income without log_index
    await record_income(
        db,
        job=job,
        amount=1_000_000,
        asset="USDC",
        tx_hash=tx_hash,
        log_index=None,
    )
    await db.commit()

    stream = IncomeStream()
    log = make_erc20_transfer_log(
        from_addr="0x" + "44" * 20,
        to_addr=wallet.address,
        value=1_000_000,
        tx_hash=tx_hash,
        log_index=5,
    )

    await stream.handle(db, [log])
    await db.commit()

    entries = (
        (
            await db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.job_id == job.id,
                    LedgerEntry.kind == LedgerKind.INCOME,
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(entries) == 1
    assert entries[0].log_index == 5


@pytest.mark.asyncio
async def test_income_direct_transfer_booked(db: AsyncSession):
    wallet = Wallet(address="0x" + "55" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-5",
        slug="agent-income-direct",
        name="Agent Direct Income",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.commit()

    stream = IncomeStream()
    tx_hash = "0x" + "55" * 32
    log = make_erc20_transfer_log(
        from_addr="0x" + "66" * 20,
        to_addr=wallet.address,
        value=500_000,
        tx_hash=tx_hash,
        log_index=1,
    )

    await stream.handle(db, [log])
    await db.commit()

    entries = (
        (
            await db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.agent_id == agent.id,
                    LedgerEntry.tx_hash == tx_hash,
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(entries) == 2  # 1 INCOME + 1 STUDIO_FEE
    income = next(e for e in entries if e.kind == LedgerKind.INCOME)
    fee = next(e for e in entries if e.kind == LedgerKind.STUDIO_FEE)
    from app.chain import network as net

    assert income.amount_atomic == 500_000
    assert income.job_id is None
    assert income.asset == net.payment_asset_address()
    assert fee.amount_atomic == 25_000  # 5% fee
    assert fee.asset == net.payment_asset_address()


@pytest.mark.asyncio
async def test_income_idempotent(db: AsyncSession):
    wallet = Wallet(address="0x" + "77" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-7",
        slug="agent-idempotent",
        name="Agent Idempotent",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.commit()

    stream = IncomeStream()
    tx_hash = "0x" + "77" * 32
    log = make_erc20_transfer_log(
        from_addr="0x" + "88" * 20,
        to_addr=wallet.address,
        value=800_000,
        tx_hash=tx_hash,
        log_index=0,
    )

    # Process first time
    await stream.handle(db, [log])
    await db.commit()

    # Process second time (same log)
    await stream.handle(db, [log])
    await db.commit()

    entries = (
        (
            await db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.agent_id == agent.id,
                    LedgerEntry.tx_hash == tx_hash,
                    LedgerEntry.kind == LedgerKind.INCOME,
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(entries) == 1


@pytest.mark.asyncio
async def test_income_before_gateway_commit_does_not_double_credit(db: AsyncSession):
    """If IncomeStream runs before Gateway commits job_id, record_income links it."""
    from app.chain import network as net

    wallet = Wallet(address="0x" + "91" * 20, chain_id=43113)
    db.add(wallet)
    await db.flush()

    agent = Agent(
        owner_id="owner-race",
        slug="agent-race",
        name="Agent Race",
        status=AgentStatus.ACTIVE,
        chain_id=43113,
        wallet_id=wallet.id,
    )
    db.add(agent)
    await db.commit()

    stream = IncomeStream()
    topics = await stream.topics(db)
    assert len(topics) == 3
    assert ("0x" + "00" * 12 + wallet.address[2:].lower()) in topics[2]

    tx_hash = "0x" + "92" * 32
    log = make_erc20_transfer_log(
        from_addr="0x" + "93" * 20,
        to_addr=wallet.address,
        value=250_000,
        tx_hash=tx_hash,
        log_index=3,
    )
    # 1. Indexer runs BEFORE job row exists -> books unlinked INCOME + STUDIO_FEE
    await stream.handle(db, [log])
    await db.commit()

    # 2. Gateway commits Job and calls record_income(job=job, tx_hash=tx_hash)
    job = Job(
        agent_id=agent.id,
        settlement_mode=agent.settlement_mode,
        client_address="0x" + "93" * 20,
        chain_id=43113,
        status=JobStatus.FUNDED,
        amount_atomic=250_000,
        asset=net.payment_asset_address(),
        payment_tx_hash=tx_hash,
    )
    db.add(job)
    await db.flush()
    await record_income(
        db,
        job=job,
        amount=250_000,
        asset=net.payment_asset_address(),
        tx_hash=tx_hash,
    )
    await db.commit()

    entries = (
        (
            await db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.agent_id == agent.id,
                    LedgerEntry.tx_hash == tx_hash,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert all(e.job_id == job.id for e in entries)
    assert all(e.log_index == 3 for e in entries)

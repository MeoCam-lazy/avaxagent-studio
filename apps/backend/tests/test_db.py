from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.control_plane.agents.models import Agent
from app.control_plane.billing.models import LedgerEntry, LedgerKind, Payout, PayoutStatus
from app.control_plane.jobs.models import Job, JobStatus
from app.core.config import SettlementMode
from tests.conftest import TestSessionLocal
from tests.factories import make_agent


@pytest.mark.asyncio
async def test_ledger_onchain_unique(db):
    """Two INCOME rows with same (chain_id, tx_hash, log_index) raise IntegrityError."""
    agent = await make_agent(db)
    entry1 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.INCOME,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=1_000_000,
        chain_id=43113,
        tx_hash="0x" + "a" * 64,
        log_index=0,
    )
    db.add(entry1)
    await db.commit()

    entry2 = LedgerEntry(
        agent_id=agent.id,
        kind=LedgerKind.INCOME,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=2_000_000,
        chain_id=43113,
        tx_hash="0x" + "a" * 64,
        log_index=0,
    )
    db.add(entry2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_payment_nonce_unique(db):
    """Two jobs sharing the same payment_nonce raises IntegrityError."""
    agent = await make_agent(db)
    nonce = "0x" + "1" * 64
    job1 = Job(
        agent_id=agent.id,
        settlement_mode=SettlementMode.X402,
        status=JobStatus.FUNDED,
        chain_id=43113,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=1_000_000,
        payment_nonce=nonce,
    )
    db.add(job1)
    await db.commit()

    job2 = Job(
        agent_id=agent.id,
        settlement_mode=SettlementMode.X402,
        status=JobStatus.FUNDED,
        chain_id=43113,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=1_000_000,
        payment_nonce=nonce,
    )
    db.add(job2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_token_amount_roundtrip(db):
    """Storing 2**255 in price_atomic reads back unchanged."""
    big_val = 2**255
    agent = await make_agent(db, slug="roundtrip-agent", price_atomic=big_val)
    await db.refresh(agent)

    assert agent.price_atomic == big_val


@pytest.mark.asyncio
async def test_token_amounts_load_as_exact_ints(db):
    """``Mapped[int]`` amounts must load as ``int``, not ``Decimal``.

    web3 rejects ``Decimal`` for ``uint256``, so a ``Decimal`` amount made every
    on-chain payout fail (found by the Fuji end-to-end suite).
    """
    agent = await make_agent(db, slug="int-agent", price_atomic=2**255 + 1)
    payout = Payout(
        agent_id=agent.id,
        owner_id=agent.owner_id,
        destination="0x" + "b" * 40,
        asset="0x5425890298aed601595a70AB815c96711a31Bc65",
        amount_atomic=10**30 + 1,
        status=PayoutStatus.REQUESTED,
    )
    db.add(payout)
    await db.commit()

    async with TestSessionLocal() as fresh:
        loaded = await fresh.get(Payout, payout.id)
        loaded_agent = await fresh.get(Agent, agent.id)

    assert type(loaded.amount_atomic) is int and loaded.amount_atomic == 10**30 + 1
    assert type(loaded_agent.price_atomic) is int and loaded_agent.price_atomic == 2**255 + 1

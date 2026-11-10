from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.factories import make_agent, make_job
from web3 import Web3

import app.data_plane.workers.tasks as worker_tasks
from app.control_plane.agents.models import AgentStatus
from app.control_plane.billing.models import LedgerEntry, LedgerKind
from app.control_plane.jobs.models import Job, JobEvent, JobStatus
from app.core.config import SettlementMode
from app.data_plane.workers.llm import AnthropicRunner


class FakeLlmRunner:
    def __init__(self, response: str = "Fake LLM result", should_fail: bool = False) -> None:
        self.response = response
        self.should_fail = should_fail
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
    ) -> str:
        self.calls.append(
            {"model": model, "system": system, "prompt": prompt, "temperature": temperature}
        )
        if self.should_fail:
            raise RuntimeError("upstream down")
        return self.response


@pytest.mark.asyncio
async def test_run_job_happy_path(db: AsyncSession, monkeypatch):
    fake_llm = FakeLlmRunner(response="Avax data analyzed successfully")
    monkeypatch.setattr(worker_tasks, "get_llm_runner", lambda: fake_llm)

    agent = await make_agent(
        db,
        status=AgentStatus.ACTIVE,
        slug="llm-agent",
        llm_config={"model": "claude-sonnet-5-5", "system_prompt": "You are a financial analyst"},
    )
    job = await make_job(
        db,
        agent,
        status=JobStatus.FUNDED,
        settlement_mode=SettlementMode.X402,
        request={"message": "Please analyze AVAX price"},
    )
    job_id = job.id
    agent_slug = agent.slug
    await db.commit()

    await worker_tasks.run_job({"session": db}, str(job_id))

    # Refresh job state
    db.expire_all()
    updated_job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert updated_job.status == JobStatus.SETTLED
    assert updated_job.deliverable_uri is not None
    assert updated_job.deliverable_hash is not None
    assert updated_job.deliverable_hash.startswith("0x")
    assert len(updated_job.deliverable_hash) == 66

    # Verify deliverable content matches computed keccak
    expected_data = {
        "job_id": str(job_id),
        "agent": agent_slug,
        "output": "Avax data analyzed successfully",
    }
    canonical = json.dumps(expected_data, sort_keys=True, separators=(",", ":"))
    expected_hash = "0x" + Web3.keccak(text=canonical).hex().removeprefix("0x")
    assert updated_job.deliverable_hash.lower() == expected_hash.lower()

    # Verify timeline events
    events = (await db.execute(select(JobEvent).where(JobEvent.job_id == job_id))).scalars().all()
    event_types = [e.type for e in events]
    assert "llm_started" in event_types
    assert "submitted" in event_types
    assert "settled" in event_types

    # Verify LLM was called with correct parameters
    assert len(fake_llm.calls) == 1
    call = fake_llm.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["system"] == "You are a financial analyst"
    assert "analyze AVAX price" in call["prompt"]


@pytest.mark.asyncio
async def test_run_job_idempotent_when_not_funded(db: AsyncSession, monkeypatch):
    fake_llm = FakeLlmRunner()
    monkeypatch.setattr(worker_tasks, "get_llm_runner", lambda: fake_llm)

    agent = await make_agent(db, status=AgentStatus.ACTIVE)
    job = await make_job(
        db,
        agent,
        status=JobStatus.SETTLED,
        settlement_mode=SettlementMode.X402,
    )
    job_id = job.id
    await db.commit()

    # Call on already-settled job
    await worker_tasks.run_job({"session": db}, str(job_id))

    # LLM should not have been called
    assert len(fake_llm.calls) == 0


@pytest.mark.asyncio
async def test_llm_error_marks_failed_keeps_income(db: AsyncSession, monkeypatch):
    fake_llm = FakeLlmRunner(should_fail=True)
    monkeypatch.setattr(worker_tasks, "get_llm_runner", lambda: fake_llm)

    agent = await make_agent(db, status=AgentStatus.ACTIVE)
    job = await make_job(
        db,
        agent,
        status=JobStatus.FUNDED,
        settlement_mode=SettlementMode.X402,
        request={"message": "Task that causes error"},
    )
    # Simulate booked income from gateway
    income = LedgerEntry(
        agent_id=agent.id,
        job_id=job.id,
        kind=LedgerKind.INCOME,
        asset="0x" + "11" * 20,
        amount_atomic=2_000_000,
        chain_id=43113,
        tx_hash="0x" + "aa" * 32,
    )
    db.add(income)
    job_id = job.id
    await db.commit()

    await worker_tasks.run_job({"session": db}, str(job_id))

    db.expire_all()
    updated_job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert updated_job.status == JobStatus.FAILED
    assert "upstream down" in (updated_job.error or "")

    events = (await db.execute(select(JobEvent).where(JobEvent.job_id == job_id))).scalars().all()
    assert any(e.type == "failed" for e in events)

    # Income row must remain untouched
    ledger_entries = (
        (await db.execute(select(LedgerEntry).where(LedgerEntry.job_id == job_id))).scalars().all()
    )
    assert len(ledger_entries) == 1
    assert ledger_entries[0].kind == LedgerKind.INCOME


@pytest.mark.asyncio
async def test_anthropic_runner_shape(monkeypatch):
    runner = AnthropicRunner(api_key="test-api-key")

    mock_response = MagicMock()
    mock_block1 = MagicMock()
    mock_block1.text = "Hello "
    mock_block2 = MagicMock()
    mock_block2.text = "World!"
    mock_response.content = [mock_block1, mock_block2]

    mock_create = AsyncMock(return_value=mock_response)

    class MockAsyncAnthropic:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.messages = MagicMock()
            self.messages.create = mock_create

    import anthropic

    monkeypatch.setattr(anthropic, "AsyncAnthropic", MockAsyncAnthropic)

    result = await runner.complete(
        model="claude-sonnet-5-5",
        system="System instruction",
        prompt="User prompt",
        temperature=0.2,
    )

    assert result == "Hello World!"
    mock_create.assert_awaited_once_with(
        model="claude-sonnet-5-5",
        max_tokens=4096,
        temperature=0.2,
        system="System instruction",
        messages=[{"role": "user", "content": "User prompt"}],
    )

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestSessionLocal
from tests.fakes import FakeChainReader

from app.core.config import settings
from app.data_plane.indexer.models import IndexerCursor
from app.data_plane.indexer.service import ChainIndexer
from app.data_plane.indexer.streams import Stream


class DummyStream(Stream):
    def __init__(self, name: str = "test.dummy", enabled: bool = True, fail: bool = False) -> None:
        super().__init__(name=name, description="dummy test stream", enabled=enabled)
        self.handled_logs: list[list[dict[str, Any]]] = []
        self.fail = fail

    async def address(self, db: AsyncSession) -> list[str]:
        return ["0x" + "11" * 20]

    async def topics(self, db: AsyncSession) -> list:
        return [["0x" + "aa" * 32]]

    async def handle(self, db: AsyncSession, logs: list[dict[str, Any]]) -> None:
        if self.fail:
            raise RuntimeError("handler failed intentionally")
        self.handled_logs.append(logs)


@pytest.mark.asyncio
async def test_resume_from_cursor(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "indexer_confirmations", 0)
    monkeypatch.setattr(settings, "indexer_start_block", 0)
    stream = DummyStream(name="stream.resume")
    chain_id = 43113

    cursor = IndexerCursor(chain_id=chain_id, stream="stream.resume", last_block=50)
    db.add(cursor)
    await db.commit()

    reader = FakeChainReader(block_number=60)
    indexer = ChainIndexer(
        session_factory=TestSessionLocal,
        reader=reader,
        streams=[stream],
        batch_size=2000,
        chain_id=chain_id,
    )

    await indexer.tick()

    assert len(reader.log_calls) == 1
    call = reader.log_calls[0]
    assert call["from_block"] == 51
    assert call["to_block"] == 60

    async with TestSessionLocal() as s:
        updated = await s.get(IndexerCursor, (chain_id, "stream.resume"))
        assert updated is not None
        assert updated.last_block == 60


@pytest.mark.asyncio
async def test_respects_confirmations(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "indexer_confirmations", 3)
    monkeypatch.setattr(settings, "indexer_start_block", 0)
    stream = DummyStream(name="stream.confirmations")
    chain_id = 43113

    reader = FakeChainReader(block_number=100)
    indexer = ChainIndexer(
        session_factory=TestSessionLocal,
        reader=reader,
        streams=[stream],
        batch_size=2000,
        chain_id=chain_id,
    )

    await indexer.tick()

    assert len(reader.log_calls) == 1
    call = reader.log_calls[0]
    assert call["from_block"] == 0
    assert call["to_block"] == 97

    async with TestSessionLocal() as s:
        updated = await s.get(IndexerCursor, (chain_id, "stream.confirmations"))
        assert updated is not None
        assert updated.last_block == 97


@pytest.mark.asyncio
async def test_chunks_large_ranges(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "indexer_confirmations", 0)
    monkeypatch.setattr(settings, "indexer_start_block", 0)
    stream = DummyStream(name="stream.chunks")
    chain_id = 43113

    reader = FakeChainReader(block_number=5000)
    indexer = ChainIndexer(
        session_factory=TestSessionLocal,
        reader=reader,
        streams=[stream],
        batch_size=2000,
        chain_id=chain_id,
    )

    await indexer.tick()

    assert len(reader.log_calls) == 3
    assert reader.log_calls[0]["from_block"] == 0
    assert reader.log_calls[0]["to_block"] == 1999
    assert reader.log_calls[1]["from_block"] == 2000
    assert reader.log_calls[1]["to_block"] == 3999
    assert reader.log_calls[2]["from_block"] == 4000
    assert reader.log_calls[2]["to_block"] == 5000

    async with TestSessionLocal() as s:
        updated = await s.get(IndexerCursor, (chain_id, "stream.chunks"))
        assert updated is not None
        assert updated.last_block == 5000


@pytest.mark.asyncio
async def test_handler_error_does_not_advance_cursor(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "indexer_confirmations", 0)
    monkeypatch.setattr(settings, "indexer_start_block", 0)
    stream = DummyStream(name="stream.error", fail=True)
    chain_id = 43113

    cursor = IndexerCursor(chain_id=chain_id, stream="stream.error", last_block=50)
    db.add(cursor)
    await db.commit()

    reader = FakeChainReader(block_number=60)
    indexer = ChainIndexer(
        session_factory=TestSessionLocal,
        reader=reader,
        streams=[stream],
        batch_size=2000,
        chain_id=chain_id,
    )

    with pytest.raises(RuntimeError, match="handler failed intentionally"):
        await indexer.tick()

    async with TestSessionLocal() as s:
        cursor_db = await s.get(IndexerCursor, (chain_id, "stream.error"))
        assert cursor_db is not None
        assert cursor_db.last_block == 50


@pytest.mark.asyncio
async def test_disabled_stream_skipped(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "indexer_confirmations", 0)
    monkeypatch.setattr(settings, "indexer_start_block", 0)
    stream = DummyStream(name="stream.disabled", enabled=False)
    chain_id = 43113

    reader = FakeChainReader(block_number=100)
    indexer = ChainIndexer(
        session_factory=TestSessionLocal,
        reader=reader,
        streams=[stream],
        batch_size=2000,
        chain_id=chain_id,
    )

    await indexer.tick()

    assert len(reader.log_calls) == 0

    async with TestSessionLocal() as s:
        cursor_db = await s.get(IndexerCursor, (chain_id, "stream.disabled"))
        assert cursor_db is None


def test_process_entrypoint_constructs_with_defaults(monkeypatch):
    """``python -m app.data_plane.indexer`` builds ``ChainIndexer()`` with no args.

    Like ``SettleBot`` / ``PayoutExecutor``, the process defaults to the app
    session factory and the configured chain reader. Without defaults the
    indexer process crashed on start (found by running the compose stack).
    """
    from app.data_plane.indexer import service

    reader = FakeChainReader()
    monkeypatch.setattr(service, "get_chain_reader", lambda: reader)

    indexer = ChainIndexer()

    assert indexer.session_factory is service.SessionLocal
    assert indexer.reader is reader

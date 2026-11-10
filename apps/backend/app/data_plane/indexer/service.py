"""Indexer loop.

Per enabled stream: read ``IndexerCursor``, ``eth_getLogs`` from
``last_block + 1`` to ``head - INDEXER_CONFIRMATIONS`` in bounded ranges
(public C-Chain RPCs cap the range), decode, filter to managed agents, write
rows / enqueue work, then advance the cursor in the same DB transaction.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chain import network as net
from app.chain.reader import ChainReader
from app.core.config import settings
from app.data_plane.indexer.models import IndexerCursor
from app.data_plane.indexer.streams import Stream, streams as default_streams

log = logging.getLogger(__name__)


class ChainIndexer:
    poll_interval_s: float = 2.0  # C-Chain block time is ~1-2 s

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
        reader: ChainReader,
        streams: list[Stream] | None = None,
        batch_size: int = 2000,
        chain_id: int | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.reader = reader
        self.streams = streams
        self.batch_size = batch_size
        self._chain_id = chain_id

    @property
    def chain_id(self) -> int:
        return self._chain_id or net.chain_id()

    async def tick(self) -> None:
        active_streams = [s for s in (self.streams or default_streams()) if s.enabled]
        if not active_streams:
            return

        head = self.reader.block_number()
        safe = head - settings.indexer_confirmations
        cid = self.chain_id

        for stream in active_streams:
            async with self.session_factory() as db:
                cursor = await db.get(IndexerCursor, (cid, stream.name))
                if cursor is not None:
                    start = max(cursor.last_block + 1, settings.indexer_start_block)
                else:
                    start = settings.indexer_start_block

                if start > safe:
                    continue

                current = start
                while current <= safe:
                    chunk_end = min(current + self.batch_size - 1, safe)

                    addr = stream.address(db)
                    if inspect.isawaitable(addr):
                        addr = await addr

                    top = stream.topics(db)
                    if inspect.isawaitable(top):
                        top = await top

                    logs = self.reader.get_logs(addr, top, current, chunk_end)

                    try:
                        await stream.handle(db, logs)
                        if cursor is None:
                            cursor = IndexerCursor(
                                chain_id=cid,
                                stream=stream.name,
                                last_block=chunk_end,
                            )
                            db.add(cursor)
                        else:
                            cursor.last_block = chunk_end
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        log.exception(
                            "Handler error on stream %s at blocks %d-%d",
                            stream.name,
                            current,
                            chunk_end,
                        )
                        raise

                    current = chunk_end + 1

    async def run(self) -> None:
        active_streams = [s.name for s in (self.streams or default_streams()) if s.enabled]
        log.info("indexer starting on chain %s, streams=%s", self.chain_id, active_streams)
        while True:
            try:
                await self.tick()
            except Exception as exc:
                log.exception("Indexer tick error: %s", exc)
            await asyncio.sleep(self.poll_interval_s)

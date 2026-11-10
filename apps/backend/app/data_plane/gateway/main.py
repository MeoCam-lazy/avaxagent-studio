"""A2A gateway ASGI app (separate process from the control-plane API).

Run: ``uvicorn app.data_plane.gateway.main:app --port 8001``
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Response

from app.chain import network as net
from app.chain.reader import ChainReader, get_chain_reader
from app.core.errors import register_exception_handlers
from app.core.queue import get_queue
from app.data_plane.gateway import service
from app.data_plane.gateway.relayer import Relayer, get_relayer
from app.data_plane.gateway.schemas import JsonRpcRequest
from app.db.session import DbSession

app = FastAPI(title="Avaxagent Studio A2A Gateway", version="0.1.0")
register_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "gateway", "chain_id": net.chain_id()}


@app.get("/agents/{slug}/.well-known/agent-card.json")
async def agent_card(slug: str, db: DbSession) -> dict[str, Any]:
    return await service.agent_card(db, slug)


@app.post("/agents/{slug}/a2a")
async def a2a(
    slug: str,
    body: JsonRpcRequest,
    db: DbSession,
    relayer: Annotated[Relayer, Depends(get_relayer)],
    chain_reader: Annotated[ChainReader, Depends(get_chain_reader)],
    queue: Annotated[Any, Depends(get_queue)],
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
) -> Response:
    return await service.handle_a2a(
        db,
        slug,
        body,
        x_payment,
        relayer=relayer,
        chain_reader=chain_reader,
        queue=queue,
    )

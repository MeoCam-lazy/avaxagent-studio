"""A2A protocol handler for agent invocations."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain.network import chain_id
from app.chain.reader import ChainReader
from app.control_plane.agents.models import AgentStatus
from app.control_plane.agents.service import AgentService
from app.control_plane.billing.ledger import record_income
from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.wallets.models import Wallet
from app.core.config import SettlementMode
from app.core.errors import FeatureDisabled
from app.core.queue import RUN_JOB
from app.data_plane.gateway.relayer import Relayer
from app.data_plane.gateway.schemas import JsonRpcRequest
from app.data_plane.gateway.x402 import (
    PaymentInvalid,
    challenge,
    decode_payment,
    verify_payment,
)


async def handle_a2a(
    db: AsyncSession,
    slug: str,
    req: JsonRpcRequest,
    x_payment: str | None,
    *,
    relayer: Relayer,
    chain_reader: ChainReader,
    queue: Any,
    now: int | None = None,
) -> Response:
    """Handle incoming JSON-RPC 2.0 requests on the /agents/{slug}/a2a endpoint."""
    agent = await AgentService(db).get_by_slug(slug)
    if not agent or agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "agent_not_found"},
        )

    if agent.settlement_mode == SettlementMode.ERC8183:
        raise FeatureDisabled("erc8183")

    # Method: tasks/get
    if req.method == "tasks/get":
        job_id_raw = req.params.get("id") or req.params.get("taskId")
        if not job_id_raw:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": req.id,
                    "error": {"code": -32602, "message": "Missing task id"},
                },
            )
        try:
            job_uuid = uuid.UUID(str(job_id_raw))
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "job_not_found"},
            ) from err

        job = (
            await db.execute(select(Job).where(Job.id == job_uuid, Job.agent_id == agent.id))
        ).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "job_not_found"},
            )

        if job.status in (JobStatus.FUNDED, JobStatus.RUNNING):
            state = "working"
        elif job.status in (JobStatus.SUBMITTED, JobStatus.SETTLED):
            state = "completed"
        elif job.status == JobStatus.FAILED:
            state = "failed"
        else:
            state = str(job.status.value)

        artifacts = []
        if job.deliverable_uri:
            artifacts.append({"name": "deliverable", "uri": job.deliverable_uri})

        result: dict[str, Any] = {
            "kind": "task",
            "id": str(job.id),
            "status": {"state": state},
            "artifacts": artifacts,
        }
        if job.error:
            result["error"] = job.error

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "jsonrpc": "2.0",
                "id": req.id,
                "result": result,
            },
        )

    # Unknown method
    if req.method != "message/send":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32601, "message": f"Method '{req.method}' not found"},
            },
        )

    # Method: message/send
    if not agent.wallet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "agent_has_no_wallet"},
        )

    wallet = (
        await db.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
    ).scalar_one_or_none()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "agent_wallet_not_found"},
        )

    ch = challenge(agent, wallet)

    # If no payment provided -> HTTP 402 Challenge
    if not x_payment:
        accepts_json = [a.model_dump(by_alias=True) for a in ch["accepts"]]
        body = {
            "x402Version": ch["x402Version"],
            "error": ch["error"],
            "accepts": accepts_json,
        }
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED, content=body)

    # Verify payment
    accept = ch["accepts"][0]
    ts = now if now is not None else int(time.time())
    try:
        auth = verify_payment(x_payment, accept=accept, now=ts)
    except PaymentInvalid as exc:
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"error": exc.reason},
        )

    # Step 1: Insert Job with unique payment_nonce
    job = Job(
        agent_id=agent.id,
        settlement_mode=SettlementMode.X402,
        status=JobStatus.FUNDED,
        chain_id=chain_id(),
        client_address=auth.from_,
        amount_atomic=int(auth.value),
        asset=accept.asset,
        payment_nonce=auth.nonce,
        request=req.params,
    )
    db.add(job)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "payment_replayed"},
        )

    # Step 2: Check on-chain authorization_used
    nonce_bytes = bytes.fromhex(auth.nonce.removeprefix("0x"))
    if chain_reader.authorization_used(accept.asset, auth.from_, nonce_bytes):
        await db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "payment_replayed"},
        )

    # Step 3: Settle payment via relayer
    payload = decode_payment(x_payment) if isinstance(x_payment, str) else x_payment
    try:
        tx_hash = relayer.settle(accept.asset, auth, payload.payload.signature)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:2000]
        await add_event(db, job, "failed", message=str(exc))
        await db.commit()
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "settlement_failed"},
        )

    job.payment_tx_hash = tx_hash
    await record_income(
        db,
        job=job,
        amount=int(auth.value),
        asset=accept.asset,
        tx_hash=tx_hash,
    )

    # Step 4: Add funded event, commit, and enqueue RUN_JOB
    await add_event(db, job, "funded", tx_hash=tx_hash)
    await db.commit()

    await queue.enqueue_job(RUN_JOB, str(job.id))

    # Step 5: Return JSON-RPC response
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "kind": "task",
                "id": str(job.id),
                "status": {"state": "submitted"},
            },
        },
    )

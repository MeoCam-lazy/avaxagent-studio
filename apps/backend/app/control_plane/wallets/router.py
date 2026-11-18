from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.chain.reader import ChainReader, get_chain_reader
from app.control_plane.wallets.schemas import WalletBalances, WalletPolicy, WalletRead
from app.control_plane.wallets.service import WalletService
from app.control_plane.wallets.turnkey_admin import TurnkeyAdmin, TurnkeyApiError, get_turnkey_admin
from app.core.security import CurrentUser
from app.db.session import DbSession

router = APIRouter(prefix="/agents/{agent_id}/wallet", tags=["wallets"])


def _turnkey_http_error(exc: TurnkeyApiError) -> HTTPException:
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "turnkey_permission_denied",
                "reason": "Turnkey API key lacks permission for this wallet operation. Check the organization policy.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "error": "turnkey_operation_failed",
            "reason": "Turnkey rejected the wallet operation.",
        },
    )


@router.post("", response_model=WalletRead, status_code=status.HTTP_201_CREATED)
async def provision_wallet(
    agent_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    admin: Annotated[TurnkeyAdmin, Depends(get_turnkey_admin)],
    reader: Annotated[ChainReader, Depends(get_chain_reader)],
) -> WalletRead:
    try:
        return await WalletService(db, admin=admin, reader=reader).provision(user.id, agent_id)
    except TurnkeyApiError as exc:
        raise _turnkey_http_error(exc) from exc


@router.get("", response_model=WalletRead)
async def get_wallet(
    agent_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    reader: Annotated[ChainReader, Depends(get_chain_reader)],
) -> WalletRead:
    return await WalletService(db, reader=reader).get(user.id, agent_id)


@router.put("/policy", response_model=WalletRead)
async def update_policy(
    agent_id: uuid.UUID,
    body: WalletPolicy,
    user: CurrentUser,
    db: DbSession,
    admin: Annotated[TurnkeyAdmin, Depends(get_turnkey_admin)],
    reader: Annotated[ChainReader, Depends(get_chain_reader)],
) -> WalletRead:
    try:
        return await WalletService(db, admin=admin, reader=reader).update_policy(
            user.id, agent_id, body
        )
    except TurnkeyApiError as exc:
        raise _turnkey_http_error(exc) from exc


@router.get("/balances", response_model=WalletBalances)
async def get_balances(
    agent_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    reader: Annotated[ChainReader, Depends(get_chain_reader)],
) -> WalletBalances:
    return await WalletService(db, reader=reader).balances(user.id, agent_id)

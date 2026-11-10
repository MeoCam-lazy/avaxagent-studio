from __future__ import annotations

import secrets
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.chain.network import chain_id
from app.core.auth.siwe import parse_siwe, verify_signature
from app.core.auth.tokens import create_access_token
from app.core.config import settings
from app.core.security import CurrentUser, User

router = APIRouter(tags=["auth"])


class NonceResponse(BaseModel):
    nonce: str


class VerifyRequest(BaseModel):
    message: str
    signature: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    address: str


def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


@router.post("/nonce", response_model=NonceResponse)
async def generate_nonce() -> NonceResponse:
    nonce = secrets.token_hex(16)
    r = get_redis()
    try:
        await r.set(f"siwe:nonce:{nonce}", "1", ex=300)
    finally:
        await r.aclose()
    return NonceResponse(nonce=nonce)


@router.post("/verify", response_model=TokenResponse)
async def verify(req: VerifyRequest) -> TokenResponse:
    siwe = parse_siwe(req.message)

    if siwe.domain.lower() != settings.auth_domain.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_domain"},
        )

    if siwe.chain_id != chain_id():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_chain_id"},
        )

    if siwe.expiration_time and siwe.expiration_time < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "siwe_expired"},
        )

    r = get_redis()
    try:
        consumed = await r.getdel(f"siwe:nonce:{siwe.nonce}")
    finally:
        await r.aclose()

    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_or_expired_nonce"},
        )

    verify_signature(req.message, req.signature, siwe.address)

    token = create_access_token(siwe.address)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        address=siwe.address,
    )


@router.get("/me", response_model=User)
async def get_me(user: CurrentUser) -> User:
    return user

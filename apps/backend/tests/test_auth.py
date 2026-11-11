from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

from app.chain.network import chain_id as get_chain_id
from app.core.config import settings


def make_siwe_message(
    address: str,
    nonce: str,
    domain: str = "localhost:5173",
    chain_id: int | None = None,
    uri: str = "http://localhost:5173",
    issued_at: str | None = None,
    expiration_time: str | None = None,
) -> str:
    if chain_id is None:
        chain_id = get_chain_id()
    if issued_at is None:
        issued_at = datetime.now(timezone.utc).isoformat()
    msg = (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{address}\n\n"
        f"Sign in with Ethereum to the app.\n\n"
        f"URI: {uri}\n"
        f"Version: 1\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}"
    )
    if expiration_time:
        msg += f"\nExpiration Time: {expiration_time}"
    return msg


def test_login_roundtrip(client: TestClient):
    nonce_res = client.post("/api/v1/auth/nonce")
    assert nonce_res.status_code == 200
    nonce = nonce_res.json()["nonce"]
    assert len(nonce) > 8

    acct = Account.create()
    msg = make_siwe_message(acct.address, nonce)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()

    verify_res = client.post(
        "/api/v1/auth/verify",
        json={"message": msg, "signature": sig},
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["address"].lower() == acct.address.lower()

    token = data["access_token"]
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["address"].lower() == acct.address.lower()


def test_nonce_single_use(client: TestClient):
    nonce_res = client.post("/api/v1/auth/nonce")
    assert nonce_res.status_code == 200
    nonce = nonce_res.json()["nonce"]

    acct = Account.create()
    msg = make_siwe_message(acct.address, nonce)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()

    verify1 = client.post(
        "/api/v1/auth/verify",
        json={"message": msg, "signature": sig},
    )
    assert verify1.status_code == 200

    verify2 = client.post(
        "/api/v1/auth/verify",
        json={"message": msg, "signature": sig},
    )
    assert verify2.status_code == 401


def test_wrong_domain_rejected(client: TestClient):
    nonce_res = client.post("/api/v1/auth/nonce")
    nonce = nonce_res.json()["nonce"]

    acct = Account.create()
    msg = make_siwe_message(acct.address, nonce, domain="evil.com")
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()

    res = client.post(
        "/api/v1/auth/verify",
        json={"message": msg, "signature": sig},
    )
    assert res.status_code == 401


def test_wrong_chain_rejected(client: TestClient):
    nonce_res = client.post("/api/v1/auth/nonce")
    nonce = nonce_res.json()["nonce"]

    acct = Account.create()
    msg = make_siwe_message(acct.address, nonce, chain_id=1)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()

    res = client.post(
        "/api/v1/auth/verify",
        json={"message": msg, "signature": sig},
    )
    assert res.status_code == 401


def test_expired_token_401(client: TestClient):
    payload = {
        "sub": "0x1234567890123456789012345678901234567890",
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401


def test_protected_route_requires_token(client: TestClient):
    res = client.get("/api/v1/agents")
    assert res.status_code == 401


def test_prod_rejects_default_jwt_secret():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(environment="production", auth_jwt_secret="dev-insecure")

    cfg = Settings(environment="production", auth_jwt_secret="super-strong-prod-secret-32b")
    assert cfg.auth_jwt_secret == "super-strong-prod-secret-32b"

from __future__ import annotations

import re
from datetime import datetime

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import HTTPException, status
from pydantic import BaseModel


class SiweMessage(BaseModel):
    domain: str
    address: str
    uri: str
    chain_id: int
    nonce: str
    issued_at: datetime
    expiration_time: datetime | None = None


def parse_siwe(message: str) -> SiweMessage:
    lines = [line.strip() for line in message.strip().splitlines() if line.strip()]
    if len(lines) < 2 or "wants you to sign in with your Ethereum account:" not in lines[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_siwe_format"},
        )

    domain_match = re.match(
        r"^([^:\s]+(?::\d+)?) wants you to sign in with your Ethereum account:$",
        lines[0],
    )
    if not domain_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_siwe_domain_line"},
        )
    domain = domain_match.group(1)

    address = lines[1]
    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_siwe_address"},
        )

    fields: dict[str, str] = {}
    for line in lines[2:]:
        if ":" in line:
            key, val = line.split(":", 1)
            fields[key.strip()] = val.strip()

    uri = fields.get("URI")
    chain_id_str = fields.get("Chain ID")
    nonce = fields.get("Nonce")
    issued_at_str = fields.get("Issued At")
    expiration_time_str = fields.get("Expiration Time")

    if not uri or not chain_id_str or not nonce or not issued_at_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_siwe_fields"},
        )

    try:
        chain_id = int(chain_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_chain_id"},
        ) from None

    try:
        issued_at = datetime.fromisoformat(issued_at_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_issued_at"},
        ) from None

    expiration_time: datetime | None = None
    if expiration_time_str:
        try:
            expiration_time = datetime.fromisoformat(expiration_time_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_expiration_time"},
            ) from None

    return SiweMessage(
        domain=domain,
        address=address,
        uri=uri,
        chain_id=chain_id,
        nonce=nonce,
        issued_at=issued_at,
        expiration_time=expiration_time,
    )


def verify_signature(message: str, signature: str, expected_address: str) -> None:
    try:
        encoded = encode_defunct(text=message)
        recovered = Account.recover_message(encoded, signature=signature)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_signature"},
        ) from None

    if recovered.lower() != expected_address.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "signature_mismatch"},
        )

"""x402 payment challenge and EIP-3009 payment verification."""

from __future__ import annotations

import base64
import json
from typing import Any

from avaxagent.x402 import resolve_x402_asset
from eth_account import Account
from eth_account.messages import encode_typed_data
from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3

from app.chain.network import caip2, chain_id, payment_asset_address, payment_asset_id
from app.data_plane.gateway.schemas import X402Accept

EIP3009_TRANSFER_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


class PaymentInvalid(RuntimeError):
    """Raised when an x402 payment payload fails decoding or verification."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Payment invalid: {reason}")
        self.reason = reason


class Authorization(BaseModel):
    """EIP-3009 TransferWithAuthorization struct parameters."""

    from_: str = Field(alias="from")
    to: str
    value: int
    validAfter: int
    validBefore: int
    nonce: str

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("value", "validAfter", "validBefore", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> int:
        return int(v)

    def __getattr__(self, name: str) -> Any:
        if name == "from":
            return self.from_
        return super().__getattr__(name)


class PaymentPayloadInner(BaseModel):
    """Inner payload containing authorization data and signature."""

    signature: str
    authorization: Authorization

    model_config = ConfigDict(populate_by_name=True)


class PaymentPayload(BaseModel):
    """Top-level x402 payment envelope (deserialized from X-PAYMENT)."""

    x402Version: int = 1
    scheme: str = "exact"
    network: str
    payload: PaymentPayloadInner

    model_config = ConfigDict(populate_by_name=True)


def challenge(agent: Any, wallet: Any) -> dict[str, Any]:
    """Build the standard HTTP 402 Payment Required response body."""
    resolved = resolve_x402_asset(chain_id(), payment_asset_id())
    accept = X402Accept(
        scheme="exact",
        network=caip2(),
        asset=payment_asset_address(),
        payTo=wallet.address,
        amount=str(int(agent.price_atomic)),
        maxTimeoutSeconds=300,
        extra={
            "name": resolved.eip3009_domain.name,
            "version": resolved.eip3009_domain.version,
        },
    )
    return {
        "x402Version": 1,
        "error": "payment_required",
        "accepts": [accept],
    }


def decode_payment(header: str) -> PaymentPayload:
    """Decode and validate a base64-encoded X-PAYMENT JSON envelope."""
    if not header or not isinstance(header, str):
        raise PaymentInvalid("bad_encoding")

    try:
        raw_json = base64.b64decode(header.strip(), validate=True)
        data = json.loads(raw_json.decode("utf-8"))
        return PaymentPayload.model_validate(data)
    except Exception as exc:
        raise PaymentInvalid("bad_encoding") from exc


def verify_payment(
    p: PaymentPayload | str,
    *,
    accept: X402Accept,
    now: int,
) -> Authorization:
    """Verify an x402 payment against an expected challenge acceptance."""
    if isinstance(p, str):
        p = decode_payment(p)

    if p.scheme != accept.scheme:
        raise PaymentInvalid("wrong_scheme")

    if p.network != accept.network:
        raise PaymentInvalid("wrong_network")

    auth = p.payload.authorization

    try:
        pay_to_cs = Web3.to_checksum_address(accept.payTo)
        auth_to_cs = Web3.to_checksum_address(auth.to)
        if auth_to_cs != pay_to_cs:
            raise PaymentInvalid("wrong_recipient")
    except PaymentInvalid:
        raise
    except Exception as exc:
        raise PaymentInvalid("wrong_recipient") from exc

    if int(auth.value) < int(accept.amount):
        raise PaymentInvalid("insufficient_value")

    if now > int(auth.validBefore):
        raise PaymentInvalid("expired")

    if now < int(auth.validAfter):
        raise PaymentInvalid("not_yet_valid")

    # Verify EIP-712 signature
    try:
        chain_id_num = (
            int(accept.network.split(":")[1]) if ":" in accept.network else int(accept.network)
        )
        domain_data = {
            "name": accept.extra.get("name", "USD Coin"),
            "version": accept.extra.get("version", "2"),
            "chainId": chain_id_num,
            "verifyingContract": Web3.to_checksum_address(accept.asset),
        }

        nonce = auth.nonce
        if isinstance(nonce, str) and not nonce.startswith("0x"):
            nonce = "0x" + nonce

        message_data = {
            "from": Web3.to_checksum_address(auth.from_),
            "to": auth_to_cs,
            "value": int(auth.value),
            "validAfter": int(auth.validAfter),
            "validBefore": int(auth.validBefore),
            "nonce": nonce,
        }

        signable = encode_typed_data(
            domain_data=domain_data,
            message_types=EIP3009_TRANSFER_TYPES,
            message_data=message_data,
        )

        recovered = Account.recover_message(signable, signature=p.payload.signature)
        if Web3.to_checksum_address(recovered) != Web3.to_checksum_address(auth.from_):
            raise PaymentInvalid("bad_signature")
    except PaymentInvalid:
        raise
    except Exception as exc:
        raise PaymentInvalid("bad_signature") from exc

    return auth

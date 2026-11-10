from __future__ import annotations

import base64
import json
import secrets
import time
from types import SimpleNamespace

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from app.chain.network import payment_asset_address
from app.data_plane.gateway.x402 import (
    Authorization,
    PaymentInvalid,
    PaymentPayload,
    PaymentPayloadInner,
    X402Accept,
    challenge,
    decode_payment,
    verify_payment,
)

FUJI_USDC = payment_asset_address()
TWA_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


def _make_signed_payment(
    signer,
    *,
    to: str,
    value: int = 1_000_000,
    valid_after: int = 0,
    valid_before: int = 9_999_999_999,
    nonce: str | None = None,
    network: str = "eip155:43113",
    scheme: str = "exact",
    domain_name: str = "USD Coin",
    domain_version: str = "2",
    asset: str = FUJI_USDC,
    signed_from: str | None = None,
) -> tuple[PaymentPayload, str]:
    if nonce is None:
        nonce = "0x" + secrets.token_hex(32)

    chain_id = int(network.split(":")[1]) if ":" in network else int(network)
    domain_data = {
        "name": domain_name,
        "version": domain_version,
        "chainId": chain_id,
        "verifyingContract": asset,
    }
    from_address = signed_from or signer.address
    msg = {
        "from": from_address,
        "to": to,
        "value": value,
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": nonce,
    }
    signable = encode_typed_data(
        domain_data=domain_data,
        message_types=TWA_TYPES,
        message_data=msg,
    )
    signed = signer.sign_message(signable)
    sig = signed.signature.hex() if hasattr(signed.signature, "hex") else str(signed.signature)
    if not sig.startswith("0x"):
        sig = "0x" + sig

    payload = PaymentPayload(
        x402Version=1,
        scheme=scheme,
        network=network,
        payload=PaymentPayloadInner(
            signature=sig,
            authorization=Authorization(
                **{
                    "from": from_address,
                    "to": to,
                    "value": value,
                    "validAfter": valid_after,
                    "validBefore": valid_before,
                    "nonce": nonce,
                }
            ),
        ),
    )
    raw = {
        "x402Version": 1,
        "scheme": scheme,
        "network": network,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": from_address,
                "to": to,
                "value": str(value),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce,
            },
        },
    }
    encoded = base64.b64encode(json.dumps(raw).encode()).decode()
    return payload, encoded


def test_challenge_shape():
    agent = SimpleNamespace(price_atomic=2_000_000)
    wallet = SimpleNamespace(address="0x" + "11" * 20)

    body = challenge(agent, wallet)
    assert body["x402Version"] == 1
    assert body["error"] == "payment_required"
    assert len(body["accepts"]) == 1

    accept = body["accepts"][0]
    assert accept.asset.lower() == FUJI_USDC.lower()
    assert accept.network == "eip155:43113"
    assert accept.amount == "2000000"
    assert accept.payTo == wallet.address
    assert accept.extra == {"name": "USD Coin", "version": "2"}


def test_valid_payment_passes():
    signer = Account.create()
    beneficiary = "0x" + "22" * 20
    now = int(time.time())

    accept = X402Accept(
        scheme="exact",
        network="eip155:43113",
        asset=FUJI_USDC,
        payTo=beneficiary,
        amount="1000000",
        extra={"name": "USD Coin", "version": "2"},
    )

    payload, encoded = _make_signed_payment(
        signer,
        to=beneficiary,
        value=1_000_000,
        valid_after=now - 100,
        valid_before=now + 500,
    )

    # 1. Verify via PaymentPayload object
    auth = verify_payment(payload, accept=accept, now=now)
    assert auth.from_.lower() == signer.address.lower()
    assert auth.to.lower() == beneficiary.lower()
    assert int(auth.value) == 1_000_000

    # 2. Verify via base64 encoded string & decode_payment
    decoded_payload = decode_payment(encoded)
    assert decoded_payload.scheme == "exact"
    auth2 = verify_payment(encoded, accept=accept, now=now)
    assert auth2.from_.lower() == signer.address.lower()


@pytest.mark.parametrize(
    ("reason", "mutate_kw"),
    [
        ("bad_encoding", {"kind": "garbage_base64"}),
        ("wrong_scheme", {"scheme": "streaming"}),
        ("wrong_network", {"network": "eip155:43114"}),
        ("wrong_recipient", {"to": "0x" + "99" * 20}),
        ("insufficient_value", {"value": 999_999}),
        ("expired", {"valid_before": 1_000_000}),
        ("not_yet_valid", {"valid_after": 2_000_000_060}),
        ("bad_signature", {"kind": "wrong_key"}),
    ],
)
def test_verify_rejects(reason: str, mutate_kw: dict):
    signer = Account.create()
    beneficiary = "0x" + "33" * 20
    now = 2_000_000_000  # Fixed timestamp

    accept = X402Accept(
        scheme="exact",
        network="eip155:43113",
        asset=FUJI_USDC,
        payTo=beneficiary,
        amount="1000000",
        extra={"name": "USD Coin", "version": "2"},
    )

    if mutate_kw.get("kind") == "garbage_base64":
        test_input = "not-a-valid-base64-json-content!!!"
    elif mutate_kw.get("kind") == "wrong_key":
        # Signature signed by other key, but claimed from signer.address
        wrong_account = Account.create()
        payload, encoded = _make_signed_payment(
            wrong_account,
            to=beneficiary,
            value=1_000_000,
            valid_after=now - 100,
            valid_before=now + 500,
            signed_from=signer.address,  # Claim signer.address, but signed with wrong_account
        )
        test_input = payload
    else:
        kwargs = {
            "to": beneficiary,
            "value": 1_000_000,
            "valid_after": now - 100,
            "valid_before": now + 500,
            "network": "eip155:43113",
            "scheme": "exact",
        }
        kwargs.update(mutate_kw)
        payload, encoded = _make_signed_payment(signer, **kwargs)
        test_input = payload

    with pytest.raises(PaymentInvalid) as exc_info:
        verify_payment(test_input, accept=accept, now=now)

    assert exc_info.value.reason == reason

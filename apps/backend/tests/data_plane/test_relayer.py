from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from app.chain.network import payment_asset_address
from app.core.errors import FeatureDisabled
from app.data_plane.gateway.relayer import TurnkeyRelayer, _Eip3009Client, _split_signature
from app.data_plane.gateway.x402 import Authorization


def test_relayer_missing_config_raises_feature_disabled(monkeypatch):
    monkeypatch.setattr("app.data_plane.gateway.relayer.settings.relayer_organization_id", None)
    monkeypatch.setattr("app.data_plane.gateway.relayer.settings.relayer_sign_with", None)

    relayer = TurnkeyRelayer()
    auth = Authorization(
        **{
            "from": "0x" + "11" * 20,
            "to": "0x" + "22" * 20,
            "value": 1_000_000,
            "validAfter": 0,
            "validBefore": 9_999_999_999,
            "nonce": "0x" + "aa" * 32,
        }
    )
    with pytest.raises(FeatureDisabled):
        relayer.settle(payment_asset_address(), auth, "0x" + "00" * 65)


def test_llm_missing_api_key_raises_feature_disabled(monkeypatch):
    from app.data_plane.workers.llm import get_llm_runner

    monkeypatch.setattr("app.data_plane.workers.llm.settings.llm_api_key", None)
    with pytest.raises(FeatureDisabled) as exc_info:
        get_llm_runner()
    assert exc_info.value.feature == "llm"
    assert exc_info.value.reason == "LLM_API_KEY not configured"


def test_split_signature_normalizes_v():
    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text="eip3009-test"))
    v, r, s = _split_signature(signed.signature.hex())
    assert v in (27, 28)
    assert len(r) == 32
    assert len(s) == 32

    # Also handles raw v in {0, 1}
    raw_v0 = signed.signature[:64] + bytes([0])
    v0, _, _ = _split_signature("0x" + raw_v0.hex())
    assert v0 == 27


def test_turnkey_relayer_settle_calls_eip3009_client(monkeypatch):
    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text="auth"))
    sig_hex = "0x" + signed.signature.hex()

    captured: dict[str, Any] = {}

    def fake_send_tx(self: _Eip3009Client, fn: Any) -> dict[str, Any]:
        captured["fn_name"] = fn.fn_name
        captured["args"] = fn.args
        return {"transactionHash": bytes.fromhex("dd" * 32), "status": 1}

    monkeypatch.setattr(_Eip3009Client, "_send_tx", fake_send_tx)

    fake_provider = MagicMock()
    fake_provider.address = "0x" + "99" * 20
    from web3 import Web3

    relayer = TurnkeyRelayer(
        organization_id="org-relayer",
        sign_with=fake_provider.address,
        w3=Web3(),
        wallet_provider=fake_provider,
    )
    auth = Authorization(
        **{
            "from": "0x" + "11" * 20,
            "to": "0x" + "22" * 20,
            "value": 2_500_000,
            "validAfter": 100,
            "validBefore": 500,
            "nonce": "0x" + "cc" * 32,
        }
    )

    tx_hash = relayer.settle(payment_asset_address(), auth, sig_hex)
    assert tx_hash == "0x" + "dd" * 32
    assert captured["fn_name"] == "transferWithAuthorization"
    assert captured["args"][2] == 2_500_000
    assert captured["args"][5] == bytes.fromhex("cc" * 32)
    assert captured["args"][6] in (27, 28)

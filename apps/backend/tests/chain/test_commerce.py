"""Unit tests for ERC-8183 CommerceClient and Solidity stack parity."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from web3 import Web3

from app.chain import commerce
from app.chain.commerce import CommerceClient, OnChainJobStatus, PolicyVerdict
from app.core.config import settings
from app.core.errors import FeatureDisabled

COMMERCE_ADDR = "0x1111111111111111111111111111111111111111"
ROUTER_ADDR = "0x2222222222222222222222222222222222222222"
POLICY_ADDR = "0x3333333333333333333333333333333333333333"
SIGNER_ADDR = "0x4444444444444444444444444444444444444444"


def _enable_commerce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "commerce_address", COMMERCE_ADDR)
    monkeypatch.setattr(settings, "router_address", ROUTER_ADDR)
    monkeypatch.setattr(settings, "policy_address", POLICY_ADDR)


def test_disabled_when_addresses_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commerce_address", None)
    monkeypatch.setattr(settings, "router_address", None)
    monkeypatch.setattr(settings, "policy_address", None)
    with pytest.raises(FeatureDisabled) as exc_info:
        CommerceClient(w3=Web3())
    assert exc_info.value.feature == "erc8183"


def test_get_job_parses_struct_and_deliverable(monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    client = CommerceClient(w3=Web3())

    digest = b"\xab" * 32
    raw_tuple = (
        7,
        "0x00000000000000000000000000000000000000c1",
        "0x00000000000000000000000000000000000000b2",
        ROUTER_ADDR,
        "Audit vault contract",
        250_000,
        9_999_999,
        int(OnChainJobStatus.SUBMITTED),
        ROUTER_ADDR,
        1_234_567,
        digest,
    )
    monkeypatch.setattr(client, "_call_with_retry", lambda _fn: raw_tuple)

    job = client.get_job(7)
    assert job["id"] == 7
    assert job["description"] == "Audit vault contract"
    assert job["budget"] == 250_000
    assert job["status"] == int(OnChainJobStatus.SUBMITTED)
    assert job["submitted_at"] == 1_234_567
    assert job["deliverable"] == "0x" + "ab" * 32


def test_submit_result_encodes_digest_and_uri(monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    signer = SimpleNamespace(address=SIGNER_ADDR)
    client = CommerceClient(wallet_provider=signer, w3=Web3())

    captured: list[Any] = []

    def _fake_send_tx(fn, **_kw):
        captured.append(fn)
        return {"transactionHash": bytes.fromhex("cd" * 32), "status": 1}

    monkeypatch.setattr(client, "_send_tx", _fake_send_tx)

    tx_hash = client.submit_result(42, "ipfs://QmResult", "0x" + "12" * 32)
    assert tx_hash == "0x" + "cd" * 32
    assert len(captured) == 1
    fn = captured[0]
    assert fn.fn_name == "submit"
    assert fn.args == (42, bytes.fromhex("12" * 32), b"ipfs://QmResult")


def test_settle_fund_refund_dispute_and_policy_verdict(monkeypatch: pytest.MonkeyPatch):
    _enable_commerce(monkeypatch)
    signer = SimpleNamespace(address=SIGNER_ADDR)
    client = CommerceClient(wallet_provider=signer, w3=Web3())

    calls: list[tuple[str, tuple]] = []

    def _fake_send_tx(fn, **_kw):
        calls.append((fn.fn_name, fn.args))
        return {"transactionHash": "ef" * 32, "status": 1}

    monkeypatch.setattr(client, "_send_tx", _fake_send_tx)
    monkeypatch.setattr(
        client,
        "_call_with_retry",
        MagicMock(return_value=(int(PolicyVerdict.APPROVED), b"\x01" * 32)),
    )

    verdict, reason = client.policy_verdict(9)
    assert verdict == int(PolicyVerdict.APPROVED)
    assert reason == "0x" + "01" * 32

    assert client.fund(9, 500_000) == "0x" + "ef" * 32
    assert client.settle(9) == "0x" + "ef" * 32
    assert client.claim_refund(9) == "0x" + "ef" * 32
    assert client.dispute(9) == "0x" + "ef" * 32

    assert calls == [
        ("fund", (9, 500_000, b"")),
        ("settle", (9, b"")),
        ("claimRefund", (9,)),
        ("dispute", (9,)),
    ]


def test_solidity_sources_cover_vendored_abi_methods():
    repo_root = Path(__file__).resolve().parents[4]
    src_dir = repo_root / "contracts" / "src"
    assert (repo_root / "contracts" / "foundry.toml").is_file()
    assert (repo_root / "contracts" / "script" / "Deploy.s.sol").is_file()
    assert (repo_root / "contracts" / "test" / "Smoke.t.sol").is_file()

    checks = {
        "AgenticCommerce": [
            "initialize",
            "createJob",
            "setBudget",
            "fund",
            "submit",
            "complete",
            "reject",
            "claimRefund",
            "getJob",
        ],
        "EvaluatorRouter": ["initialize", "setPolicyWhitelist", "registerJob", "settle"],
        "OptimisticPolicy": ["onSubmitted", "dispute", "voteReject", "check"],
    }

    for contract_name, expected_fns in checks.items():
        abi_fns = {
            item["name"]
            for item in commerce.load_abi(contract_name)
            if item.get("type") == "function"
        }
        sol_text = (src_dir / f"{contract_name}.sol").read_text(encoding="utf-8")
        for fn_name in expected_fns:
            assert fn_name in abi_fns
            assert f"function {fn_name}(" in sol_text

from __future__ import annotations

import json

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.control_plane.wallets.schemas import WalletPolicy
from app.control_plane.wallets.turnkey_admin import (
    HttpTurnkeyAdmin,
    TurnkeyApiError,
    get_turnkey_admin,
)
from app.core.config import settings
from app.core.errors import FeatureDisabled


def _p256_fixture() -> tuple[str, str]:
    private = (
        int("d9" * 32, 16)
        % (0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551 - 1)
        + 1
    )
    key = ec.derive_private_key(private, ec.SECP256R1())
    public = key.public_key().public_bytes(Encoding.X962, PublicFormat.CompressedPoint)
    return format(private, "064x"), public.hex()


@pytest.mark.asyncio
async def test_create_sub_org_request_shape():
    priv, pub = _p256_fixture()
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path == "/public/v1/submit/create_sub_organization":
            return httpx.Response(
                200,
                json={
                    "activity": {
                        "id": "act-1",
                        "status": "ACTIVITY_STATUS_COMPLETED",
                        "type": "ACTIVITY_TYPE_CREATE_SUB_ORGANIZATION_V7",
                        "result": {
                            "createSubOrganizationResultV7": {
                                "subOrganizationId": "sub-123",
                                "wallet": {
                                    "walletId": "w-456",
                                    "addresses": ["0x5425890298aed601595a70ab815c96711a31bc65"],
                                },
                            }
                        },
                    }
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    admin = HttpTurnkeyAdmin(
        base_url="https://api.turnkey.com",
        api_public_key=pub,
        api_private_key=priv,
        organization_id="org-parent-1",
        transport=transport,
    )

    sub_org = await admin.create_agent_sub_org("test-agent")
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.url.path == "/public/v1/submit/create_sub_organization"
    assert "x-stamp" in req.headers
    body = json.loads(req.content.decode("utf-8"))
    assert body["type"] == "ACTIVITY_TYPE_CREATE_SUB_ORGANIZATION_V7"
    assert body["organizationId"] == "org-parent-1"
    assert body["parameters"]["subOrganizationName"] == "test-agent"
    accounts = body["parameters"]["wallet"]["accounts"]
    assert accounts[0]["path"] == "m/44'/60'/0'/0/0"
    assert accounts[0]["addressFormat"] == "ADDRESS_FORMAT_ETHEREUM"
    assert sub_org.sub_org_id == "sub-123"


@pytest.mark.asyncio
async def test_create_sub_org_parses_address():
    priv, pub = _p256_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "activity": {
                    "id": "act-2",
                    "status": "ACTIVITY_STATUS_COMPLETED",
                    "type": "ACTIVITY_TYPE_CREATE_SUB_ORGANIZATION_V7",
                    "result": {
                        "createSubOrganizationResultV7": {
                            "subOrganizationId": "sub-parsed",
                            "wallet": {
                                "walletId": "w-parsed",
                                "addresses": ["0x000000000000000000000000000000000000dead"],
                            },
                        }
                    },
                }
            },
        )

    transport = httpx.MockTransport(handler)
    admin = HttpTurnkeyAdmin(
        base_url="https://api.turnkey.com",
        api_public_key=pub,
        api_private_key=priv,
        organization_id="org-parent-1",
        transport=transport,
    )

    sub_org = await admin.create_agent_sub_org("another-agent")
    assert sub_org.sub_org_id == "sub-parsed"
    assert sub_org.wallet_id == "w-parsed"
    assert sub_org.address == "0x000000000000000000000000000000000000dead"


@pytest.mark.asyncio
async def test_policy_condition_includes_usdc():
    priv, pub = _p256_fixture()
    captured_requests: list[httpx.Request] = []
    usdc_addr = "0x5425890298aed601595a70ab815c96711a31bc65"

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "activity": {
                    "id": "act-3",
                    "status": "ACTIVITY_STATUS_COMPLETED",
                    "type": "ACTIVITY_TYPE_CREATE_POLICY_V3",
                    "result": {
                        "createPolicyResultV3": {
                            "policyId": "policy-xyz",
                        }
                    },
                }
            },
        )

    transport = httpx.MockTransport(handler)
    admin = HttpTurnkeyAdmin(
        base_url="https://api.turnkey.com",
        api_public_key=pub,
        api_private_key=priv,
        organization_id="org-parent-1",
        transport=transport,
    )

    policy_id = await admin.set_policy(
        sub_org_id="sub-123",
        policy=WalletPolicy(),
        chain_id=43113,
        allowed_eip712_contracts=[usdc_addr],
    )
    assert policy_id == "policy-xyz"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.url.path == "/public/v1/submit/create_policy"
    body = json.loads(req.content.decode("utf-8"))
    assert body["type"] == "ACTIVITY_TYPE_CREATE_POLICY_V3"
    assert body["parameters"]["effect"] == "EFFECT_ALLOW"
    assert usdc_addr.lower() in body["parameters"]["condition"]


@pytest.mark.asyncio
async def test_activity_failed_raises():
    priv, pub = _p256_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "activity": {
                    "id": "act-fail",
                    "status": "ACTIVITY_STATUS_FAILED",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    admin = HttpTurnkeyAdmin(
        base_url="https://api.turnkey.com",
        api_public_key=pub,
        api_private_key=priv,
        organization_id="org-parent-1",
        transport=transport,
    )

    with pytest.raises(TurnkeyApiError):
        await admin.create_agent_sub_org("fail-agent")


def test_missing_config_feature_disabled(monkeypatch):
    monkeypatch.setattr(settings, "turnkey_organization_id", None)
    monkeypatch.setattr(settings, "turnkey_api_public_key", None)
    monkeypatch.setattr(settings, "turnkey_api_private_key", None)

    with pytest.raises(FeatureDisabled):
        get_turnkey_admin()

"""Turnkey admin client for agent sub-org provisioning and spending policies.

Doc URL: https://docs.turnkey.com/api
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from avaxagent.wallets.turnkey.stamper import ApiKeyStamper

from app.control_plane.wallets.schemas import WalletPolicy
from app.core.config import settings
from app.core.errors import FeatureDisabled


@dataclass(frozen=True)
class SubOrg:
    sub_org_id: str
    wallet_id: str
    address: str


class TurnkeyApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        activity_status: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.activity_status = activity_status


class TurnkeyAdmin(Protocol):
    async def create_agent_sub_org(self, name: str) -> SubOrg: ...

    async def set_policy(
        self,
        sub_org_id: str,
        policy: WalletPolicy,
        *,
        chain_id: int,
        allowed_eip712_contracts: list[str],
    ) -> str: ...


class HttpTurnkeyAdmin:
    def __init__(
        self,
        *,
        base_url: str,
        api_public_key: str,
        api_private_key: str,
        organization_id: str,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.organization_id = organization_id
        self.api_public_key = api_public_key
        self.stamper = ApiKeyStamper(
            api_public_key=api_public_key,
            api_private_key=api_private_key,
        )
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"base_url": self.base_url}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.AsyncClient(**kwargs)

    async def _submit_and_wait(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_str = json.dumps(payload, separators=(",", ":"))
        header_name, header_value = self.stamper.stamp(payload_str)
        headers = {
            "Content-Type": "application/json",
            header_name: header_value,
        }

        async with self._client() as client:
            resp = await client.post(path, content=payload_str, headers=headers)
            if resp.status_code >= 400:
                raise TurnkeyApiError(
                    f"Turnkey HTTP error {resp.status_code}: {resp.text}",
                    status_code=resp.status_code,
                )
            data = resp.json()
            activity = data.get("activity", {})
            status = activity.get("status")

            attempts = 0
            while (
                status in ("ACTIVITY_STATUS_PENDING", "ACTIVITY_STATUS_CREATED")
                and attempts < 10
            ):
                attempts += 1
                await asyncio.sleep(0.5)
                poll_payload = {
                    "organizationId": payload.get("organizationId", self.organization_id),
                    "activityId": activity.get("id"),
                }
                poll_str = json.dumps(poll_payload, separators=(",", ":"))
                h_name, h_val = self.stamper.stamp(poll_str)
                poll_resp = await client.post(
                    "/public/v1/query/get_activity",
                    content=poll_str,
                    headers={"Content-Type": "application/json", h_name: h_val},
                )
                if poll_resp.status_code >= 400:
                    raise TurnkeyApiError(
                        f"Turnkey poll error {poll_resp.status_code}: {poll_resp.text}",
                        status_code=poll_resp.status_code,
                    )
                activity = poll_resp.json().get("activity", {})
                status = activity.get("status")

            if status != "ACTIVITY_STATUS_COMPLETED":
                raise TurnkeyApiError(
                    f"Activity ended with status {status}",
                    activity_status=status,
                )

            return activity.get("result", {})

    async def create_agent_sub_org(self, name: str) -> SubOrg:
        timestamp_ms = str(int(time.time() * 1000))
        payload = {
            "type": "ACTIVITY_TYPE_CREATE_SUB_ORGANIZATION_V7",
            "organizationId": self.organization_id,
            "parameters": {
                "subOrganizationName": name,
                "rootUsers": [
                    {
                        "userName": "Studio Root",
                        "apiKeys": [
                            {
                                "apiKeyName": "Studio API Key",
                                "publicKey": self.api_public_key,
                            }
                        ],
                        "authenticators": [],
                        "oauthProviders": [],
                    }
                ],
                "rootQuorumThreshold": 1,
                "wallet": {
                    "walletName": "Default Wallet",
                    "accounts": [
                        {
                            "curve": "CURVE_SECP256K1",
                            "pathFormat": "PATH_FORMAT_BIP32",
                            "path": "m/44'/60'/0'/0/0",
                            "addressFormat": "ADDRESS_FORMAT_ETHEREUM",
                        }
                    ],
                },
            },
            "timestampMs": timestamp_ms,
        }

        result = await self._submit_and_wait(
            "/public/v1/submit/create_sub_organization",
            payload,
        )
        inner = result.get("createSubOrganizationResultV7") or result
        sub_org_id = inner.get("subOrganizationId", "")
        wallet = inner.get("wallet", {})
        wallet_id = wallet.get("walletId", "")
        addresses = wallet.get("addresses", [])
        address = addresses[0] if addresses else ""

        return SubOrg(sub_org_id=sub_org_id, wallet_id=wallet_id, address=address)

    async def set_policy(
        self,
        sub_org_id: str,
        policy: WalletPolicy,
        *,
        chain_id: int,
        allowed_eip712_contracts: list[str],
    ) -> str:
        timestamp_ms = str(int(time.time() * 1000))
        all_contracts = set(c.lower() for c in policy.allowed_contracts)
        for c in allowed_eip712_contracts:
            all_contracts.add(c.lower())

        contracts_str = ", ".join(f"'{c}'" for c in sorted(all_contracts))
        condition = (
            f"eth.tx.to in [{contracts_str}] || eip712.verifyingContract in [{contracts_str}]"
        )

        payload = {
            "type": "ACTIVITY_TYPE_CREATE_POLICY_V3",
            "organizationId": sub_org_id,
            "parameters": {
                "policyName": "Agent Spending Guardrail",
                "condition": condition,
                "consensus": "true",
                "effect": "EFFECT_ALLOW",
            },
            "timestampMs": timestamp_ms,
        }

        result = await self._submit_and_wait("/public/v1/submit/create_policy", payload)
        inner = result.get("createPolicyResultV3") or result
        return inner.get("policyId", "")


def get_turnkey_admin() -> TurnkeyAdmin:
    if (
        not settings.turnkey_organization_id
        or not settings.turnkey_api_public_key
        or not settings.turnkey_api_private_key
    ):
        raise FeatureDisabled("wallets", "TURNKEY_* not configured")

    return HttpTurnkeyAdmin(
        base_url=settings.turnkey_api_base_url,
        api_public_key=settings.turnkey_api_public_key,
        api_private_key=settings.turnkey_api_private_key,
        organization_id=settings.turnkey_organization_id,
    )

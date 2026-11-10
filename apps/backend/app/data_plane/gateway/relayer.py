"""Settlement relayer protocol and Turnkey implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.config import settings
from app.core.errors import FeatureDisabled
from app.data_plane.gateway.x402 import Authorization


@runtime_checkable
class Relayer(Protocol):
    """Submits EIP-3009 transferWithAuthorization on-chain and pays AVAX gas."""

    def settle(self, token: str, auth: Authorization, signature: str) -> str:
        """Submit the authorization on-chain and return the transaction hash."""
        ...


class TurnkeyRelayer:
    """Relayer that signs and broadcasts via the studio Turnkey relayer wallet."""

    def __init__(
        self,
        organization_id: str | None = None,
        sign_with: str | None = None,
    ) -> None:
        self.organization_id = organization_id or settings.relayer_organization_id
        self.sign_with = sign_with or settings.relayer_sign_with

    def settle(self, token: str, auth: Authorization, signature: str) -> str:
        if not self.organization_id or not self.sign_with:
            raise FeatureDisabled("relayer")

        raise NotImplementedError("Live TurnkeyRelayer on-chain broadcasting")


def get_relayer() -> Relayer:
    return TurnkeyRelayer()

"""Wallet provider factories for agent runtime signing."""

from __future__ import annotations

from avaxagent.signing import SigningPolicy
from avaxagent.wallets import WalletProvider
from avaxagent.wallets.turnkey import TurnkeyWalletProvider

from app.chain.network import chain_id
from app.control_plane.wallets.models import Wallet
from app.core.config import settings
from app.core.errors import FeatureDisabled


def agent_signer(wallet: Wallet) -> WalletProvider:
    """Build a TurnkeyWalletProvider for the given agent wallet."""
    policy_dict = wallet.policy or {}
    allowed_contracts = policy_dict.get("allowed_contracts", [])
    signing_policy = SigningPolicy.strict_default()
    if allowed_contracts:
        extra_domains = frozenset((wallet.chain_id, c) for c in allowed_contracts)
        signing_policy = signing_policy.extend(domain_allowlist=extra_domains)

    return TurnkeyWalletProvider(
        organization_id=wallet.turnkey_sub_org_id or "",
        sign_with=wallet.address,
        api_public_key=settings.turnkey_api_public_key or "",
        api_private_key=settings.turnkey_api_private_key or "",
        api_base_url=settings.turnkey_api_base_url,
        expected_chain_id=chain_id(),
        signing_policy=signing_policy,
    )


def relayer_signer() -> WalletProvider:
    """Build a TurnkeyWalletProvider for the studio relayer / settle bot wallet."""
    if (
        not settings.relayer_organization_id
        or not settings.relayer_sign_with
        or not settings.turnkey_api_public_key
        or not settings.turnkey_api_private_key
    ):
        raise FeatureDisabled("relayer", "RELAYER_* or TURNKEY_API_* not configured")

    return TurnkeyWalletProvider(
        organization_id=settings.relayer_organization_id,
        sign_with=settings.relayer_sign_with,
        api_public_key=settings.turnkey_api_public_key,
        api_private_key=settings.turnkey_api_private_key,
        api_base_url=settings.turnkey_api_base_url,
        expected_chain_id=chain_id(),
        signing_policy=SigningPolicy.strict_default(),
    )

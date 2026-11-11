"""Settlement relayer protocol and Turnkey implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from avaxagent.core import create_web3
from avaxagent.core.contract_mixin import ContractClientMixin
from avaxagent.signing import SigningPolicy
from avaxagent.wallets import WalletProvider
from avaxagent.wallets.turnkey import TurnkeyWalletProvider
from web3 import Web3

from app.chain.network import chain_id, network
from app.core.config import settings
from app.core.errors import FeatureDisabled
from app.data_plane.gateway.x402 import Authorization

TRANSFER_WITH_AUTHORIZATION_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "uint256", "name": "validAfter", "type": "uint256"},
            {"internalType": "uint256", "name": "validBefore", "type": "uint256"},
            {"internalType": "bytes32", "name": "nonce", "type": "bytes32"},
            {"internalType": "uint8", "name": "v", "type": "uint8"},
            {"internalType": "bytes32", "name": "r", "type": "bytes32"},
            {"internalType": "bytes32", "name": "s", "type": "bytes32"},
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def _split_signature(signature: str) -> tuple[int, bytes, bytes]:
    sig_bytes = bytes.fromhex(signature.removeprefix("0x"))
    if len(sig_bytes) != 65:
        raise ValueError(f"Expected 65-byte ECDSA signature, got {len(sig_bytes)} bytes")
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    if v < 27:
        v += 27
    return v, r, s


class _Eip3009Client(ContractClientMixin):
    def __init__(self, w3: Web3, token_address: str, wallet_provider: WalletProvider) -> None:
        self.w3 = w3
        self.address = Web3.to_checksum_address(token_address)
        self.contract = self.w3.eth.contract(
            address=self.address, abi=TRANSFER_WITH_AUTHORIZATION_ABI
        )
        self._wallet_provider = wallet_provider
        self._account = wallet_provider.address

    def transfer_with_authorization(
        self,
        *,
        from_addr: str,
        to_addr: str,
        value: int,
        valid_after: int,
        valid_before: int,
        nonce: bytes,
        v: int,
        r: bytes,
        s: bytes,
    ) -> str:
        fn = self.contract.functions.transferWithAuthorization(
            Web3.to_checksum_address(from_addr),
            Web3.to_checksum_address(to_addr),
            int(value),
            int(valid_after),
            int(valid_before),
            nonce,
            v,
            r,
            s,
        )
        result = self._send_tx(fn)
        tx_hash = result["transactionHash"]
        text = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
        return text if text.startswith("0x") else "0x" + text


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
        *,
        w3: Web3 | None = None,
        wallet_provider: WalletProvider | None = None,
    ) -> None:
        self.organization_id = organization_id or settings.relayer_organization_id
        self.sign_with = sign_with or settings.relayer_sign_with
        self._w3 = w3
        self._wallet_provider = wallet_provider

    def _provider(self) -> WalletProvider:
        if self._wallet_provider is not None:
            return self._wallet_provider
        if (
            not self.organization_id
            or not self.sign_with
            or not settings.turnkey_api_public_key
            or not settings.turnkey_api_private_key
        ):
            raise FeatureDisabled("relayer", "RELAYER_* or TURNKEY_API_* not configured")
        self._wallet_provider = TurnkeyWalletProvider(
            organization_id=self.organization_id,
            sign_with=self.sign_with,
            api_public_key=settings.turnkey_api_public_key,
            api_private_key=settings.turnkey_api_private_key,
            api_base_url=settings.turnkey_api_base_url,
            expected_chain_id=chain_id(),
            signing_policy=SigningPolicy.strict_default(),
        )
        return self._wallet_provider

    def _web3(self) -> Web3:
        if self._w3 is None:
            self._w3 = create_web3(network().rpc_url)
        return self._w3

    def settle(self, token: str, auth: Authorization, signature: str) -> str:
        if self._wallet_provider is None and (not self.organization_id or not self.sign_with):
            raise FeatureDisabled("relayer", "RELAYER_* not configured")

        provider = self._provider()
        w3 = self._web3()
        v, r, s = _split_signature(signature)
        nonce_bytes = bytes.fromhex(auth.nonce.removeprefix("0x"))
        if len(nonce_bytes) != 32:
            raise ValueError("EIP-3009 nonce must be 32 bytes")

        client = _Eip3009Client(w3, token, provider)
        return client.transfer_with_authorization(
            from_addr=auth.from_,
            to_addr=auth.to,
            value=auth.value,
            valid_after=auth.validAfter,
            valid_before=auth.validBefore,
            nonce=nonce_bytes,
            v=v,
            r=r,
            s=s,
        )


def get_relayer() -> Relayer:
    return TurnkeyRelayer()

"""ERC-8183 agentic-commerce contracts on Avalanche (studio-deployed).

The upstream stack (AgenticCommerce kernel, EvaluatorRouter, OptimisticPolicy)
has no public Avalanche deployment, and the avaxagent SDK does not ship an
ERC-8183 client. The studio therefore:

1. deploys the three contracts to Fuji/mainnet itself (``contracts/``),
2. sets ``COMMERCE_ADDRESS`` / ``ROUTER_ADDRESS`` / ``POLICY_ADDRESS``,
3. talks to them with web3 + the ABIs vendored in ``app/chain/abis/``.

Until all three addresses are configured, everything here reports disabled and
callers fall back to x402 settlement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from avaxagent.core import create_web3
from avaxagent.core.contract_mixin import ContractClientMixin
from web3 import Web3

from app.chain.network import network
from app.core.config import settings
from app.core.errors import FeatureDisabled

ABI_DIR = Path(__file__).parent / "abis"

#: Event the chain indexer watches to enqueue jobs (escrow funded by a client).
JOB_FUNDED_EVENT = "JobFunded"


class OnChainJobStatus(IntEnum):
    OPEN = 0
    FUNDED = 1
    SUBMITTED = 2
    COMPLETED = 3
    REJECTED = 4
    EXPIRED = 5


class PolicyVerdict(IntEnum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2


@dataclass(frozen=True)
class CommerceContracts:
    commerce: str
    router: str
    policy: str


@lru_cache
def load_abi(name: str) -> list[dict[str, Any]]:
    """Load a vendored ABI: ``AgenticCommerce`` | ``EvaluatorRouter`` | ``OptimisticPolicy``."""
    data = json.loads((ABI_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data["abi"] if isinstance(data, dict) else data


def contracts() -> CommerceContracts:
    """Configured ERC-8183 addresses, or ``FeatureDisabled`` (HTTP 409)."""
    if not settings.commerce_enabled:
        raise FeatureDisabled(
            "erc8183",
            "ERC-8183 is not deployed on Avalanche; deploy contracts/ and set "
            "COMMERCE_ADDRESS, ROUTER_ADDRESS and POLICY_ADDRESS",
        )
    assert settings.commerce_address and settings.router_address and settings.policy_address
    return CommerceContracts(
        commerce=settings.commerce_address,
        router=settings.router_address,
        policy=settings.policy_address,
    )


def _normalize_bytes32(value: bytes | str) -> bytes:
    if isinstance(value, str):
        raw = bytes.fromhex(value.removeprefix("0x"))
    else:
        raw = bytes(value)
    if len(raw) != 32:
        raise ValueError(f"Expected 32-byte digest, got {len(raw)} bytes")
    return raw


def _normalize_tx_hash(tx_hash: Any) -> str:
    text = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    return text if text.startswith("0x") else "0x" + text


class CommerceClient(ContractClientMixin):
    """web3 wrapper for the studio's ERC-8183 deployment on Avalanche."""

    def __init__(
        self,
        wallet_provider: Any | None = None,
        *,
        w3: Web3 | None = None,
    ) -> None:
        self.contracts = contracts()
        self.w3 = w3 if w3 is not None else create_web3(network().rpc_url)
        self._wallet_provider = wallet_provider
        self._account = wallet_provider.address if wallet_provider is not None else None

        self.commerce_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contracts.commerce),
            abi=load_abi("AgenticCommerce"),
        )
        self.router_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contracts.router),
            abi=load_abi("EvaluatorRouter"),
        )
        self.policy_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contracts.policy),
            abi=load_abi("OptimisticPolicy"),
        )

    def get_job(self, job_id: int) -> dict[str, Any]:
        """Read ``IACP.Job`` tuple from ``AgenticCommerce.getJob(jobId)``."""
        raw = self._call_with_retry(self.commerce_contract.functions.getJob(int(job_id)))
        deliverable_raw = raw[10]
        if isinstance(deliverable_raw, (bytes, bytearray)):
            deliverable_hex = "0x" + bytes(deliverable_raw).hex()
        else:
            deliverable_hex = str(deliverable_raw)
        return {
            "id": int(raw[0]),
            "client": str(raw[1]),
            "provider": str(raw[2]),
            "evaluator": str(raw[3]),
            "description": str(raw[4]),
            "budget": int(raw[5]),
            "expired_at": int(raw[6]),
            "status": int(raw[7]),
            "hook": str(raw[8]),
            "submitted_at": int(raw[9]),
            "deliverable": deliverable_hex,
        }

    def job_payment_token(self, job_id: int) -> str:
        """Return ERC-20 token bound to ``job_id`` on ``AgenticCommerce``."""
        addr = self._call_with_retry(self.commerce_contract.functions.jobPaymentToken(int(job_id)))
        return str(addr)

    def policy_verdict(self, job_id: int, evidence: bytes = b"") -> tuple[int, str]:
        """Query ``OptimisticPolicy.check(jobId, evidence) -> (verdict, reason)``."""
        verdict, reason = self._call_with_retry(
            self.policy_contract.functions.check(int(job_id), evidence)
        )
        reason_hex = (
            "0x" + bytes(reason).hex() if isinstance(reason, (bytes, bytearray)) else str(reason)
        )
        return int(verdict), reason_hex

    def fund(self, job_id: int, expected_budget: int, opt_params: bytes = b"") -> str:
        """Client funds an open escrow job on ``AgenticCommerce``."""
        fn = self.commerce_contract.functions.fund(int(job_id), int(expected_budget), opt_params)
        res = self._send_tx(fn)
        return _normalize_tx_hash(res["transactionHash"])

    def submit_result(
        self, job_id: int, deliverable_uri: str, deliverable_hash: bytes | str
    ) -> str:
        """Provider submits the deliverable hash + URI on ``AgenticCommerce``."""
        digest = _normalize_bytes32(deliverable_hash)
        opt_params = deliverable_uri.encode("utf-8")
        fn = self.commerce_contract.functions.submit(int(job_id), digest, opt_params)
        res = self._send_tx(fn)
        return _normalize_tx_hash(res["transactionHash"])

    def settle(self, job_id: int, evidence: bytes = b"") -> str:
        """Permissionless ``EvaluatorRouter.settle(jobId, evidence)`` once policy decides."""
        fn = self.router_contract.functions.settle(int(job_id), evidence)
        res = self._send_tx(fn)
        return _normalize_tx_hash(res["transactionHash"])

    def claim_refund(self, job_id: int) -> str:
        """Refund expired escrow job via ``AgenticCommerce.claimRefund(jobId)``."""
        fn = self.commerce_contract.functions.claimRefund(int(job_id))
        res = self._send_tx(fn)
        return _normalize_tx_hash(res["transactionHash"])

    def dispute(self, job_id: int) -> str:
        """Client raises dispute within window via ``OptimisticPolicy.dispute(jobId)``."""
        fn = self.policy_contract.functions.dispute(int(job_id))
        res = self._send_tx(fn)
        return _normalize_tx_hash(res["transactionHash"])


def erc8183_client(
    wallet_provider: Any | None = None,
    *,
    w3: Web3 | None = None,
) -> CommerceClient:
    """Factory seam for constructing ``CommerceClient`` (easy to stub in unit tests)."""
    return CommerceClient(wallet_provider=wallet_provider, w3=w3)

"""Live Avalanche Fuji end-to-end tests (opt-in).

They only run with ``FUJI_E2E=1`` and talk to the RPC in ``RPC_URL`` (the
studio setting; it defaults to the public Fuji RPC). Two ways to run them:

* **Fork** (``FUJI_FORK=1``, ``RPC_URL`` pointing at ``anvil --fork-url
  <fuji>``): real Fuji contracts (USDC, ERC-8004 registry) on a local fork.
  The tests create throwaway accounts and fund them with anvil cheatcodes,
  so no faucet or key is needed. See ``make fuji-fork``.
* **Live Fuji**: real transactions, paid from three test-only keys you fund
  from faucets beforehand:

  - ``FUJI_PAYER_KEY``: holds USDC (pays for the agent call, needs no AVAX);
  - ``FUJI_RELAYER_KEY``: holds AVAX (relays the x402 transfer, pays gas);
  - ``FUJI_AGENT_KEY``: holds AVAX (stands in for the agent's Turnkey wallet:
    registers on ERC-8004, sends the payout and the fee sweep).

Only the custody layer is swapped: the agent and relayer sign with local keys
instead of Turnkey. Everything else (API, gateway, worker, settler, the
chain) is the real code path. Keys are read from the environment and never
printed.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_account.signers.local import LocalAccount
from web3 import Web3

from app.chain import network as net

FUJI_CHAIN_ID = 43113

ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "name",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "version",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "DOMAIN_SEPARATOR",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "name": "transferWithAuthorization",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"},
        ],
        "outputs": [],
    },
]

OWNER_OF_ABI = [
    {
        "name": "ownerOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "outputs": [{"name": "", "type": "address"}],
    }
]

TRANSFER_WITH_AUTHORIZATION_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(reason="live Fuji tests: set FUJI_E2E=1 (see tests/fuji/conftest.py)")
    for item in items:
        if "tests/fuji/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.fuji)
            if os.getenv("FUJI_E2E") != "1":
                item.add_marker(skip)


def is_fork() -> bool:
    return os.getenv("FUJI_FORK") == "1"


@pytest.fixture(scope="session")
def w3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(net.network().rpc_url, request_kwargs={"timeout": 30}))
    assert w3.eth.chain_id == FUJI_CHAIN_ID, f"RPC is not Fuji: chain {w3.eth.chain_id}"
    return w3


@pytest.fixture(scope="session")
def usdc(w3: Web3):
    return w3.eth.contract(
        address=Web3.to_checksum_address(net.payment_asset_address()), abi=ERC20_ABI
    )


def sign_authorization(
    account: LocalAccount,
    accept: dict,
    *,
    value: int | None = None,
    valid_for: int = 300,
    now: int,
) -> dict:
    """Sign an EIP-3009 transfer for a 402 ``accepts[]`` entry, as an x402 client does."""
    auth = {
        "from": account.address,
        "to": Web3.to_checksum_address(accept["payTo"]),
        "value": int(accept["amount"]) if value is None else value,
        "validAfter": now - 60,
        "validBefore": now + valid_for,
        "nonce": "0x" + secrets.token_hex(32),
    }
    signable = encode_typed_data(
        domain_data={
            "name": accept["extra"]["name"],
            "version": accept["extra"]["version"],
            "chainId": int(accept["network"].split(":")[1]),
            "verifyingContract": Web3.to_checksum_address(accept["asset"]),
        },
        message_types=TRANSFER_WITH_AUTHORIZATION_TYPES,
        message_data=auth,
    )
    signature = account.sign_message(signable).signature.to_0x_hex()
    return {"authorization": auth, "signature": signature}


# ── Funded accounts ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FujiAccounts:
    payer: LocalAccount
    relayer: LocalAccount
    agent: LocalAccount


def _env_account(name: str) -> LocalAccount:
    key = os.getenv(name)
    if not key:
        pytest.skip(f"live Fuji: {name} is not set (or run against a fork with FUJI_FORK=1)")
    return Account.from_key(key)


def _fork_set_usdc_balance(w3: Web3, usdc, holder: str, amount: int) -> None:
    """Write ``balances[holder]`` in the token's storage (finds the mapping slot)."""
    for slot in range(32):
        key = Web3.solidity_keccak(["uint256", "uint256"], [int(holder, 16), slot])
        w3.provider.make_request(
            "anvil_setStorageAt", [usdc.address, key.to_0x_hex(), "0x" + f"{amount:064x}"]
        )
        if usdc.functions.balanceOf(holder).call() == amount:
            return
        w3.provider.make_request(
            "anvil_setStorageAt", [usdc.address, key.to_0x_hex(), "0x" + "0" * 64]
        )
    raise RuntimeError("could not locate the token balances slot on the fork")


@pytest.fixture(scope="session")
def accounts(w3: Web3, usdc) -> FujiAccounts:
    if not is_fork():
        return FujiAccounts(
            payer=_env_account("FUJI_PAYER_KEY"),
            relayer=_env_account("FUJI_RELAYER_KEY"),
            agent=_env_account("FUJI_AGENT_KEY"),
        )
    funded = FujiAccounts(payer=Account.create(), relayer=Account.create(), agent=Account.create())
    for acct in (funded.relayer, funded.agent):
        w3.provider.make_request("anvil_setBalance", [acct.address, hex(10 * 10**18)])
    _fork_set_usdc_balance(w3, usdc, funded.payer.address, 50 * 10**6)
    return funded


@pytest.fixture
def wait_receipt(w3: Web3) -> Callable[[str], dict]:
    def _wait(tx_hash: str) -> dict:
        return dict(w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120))

    return _wait

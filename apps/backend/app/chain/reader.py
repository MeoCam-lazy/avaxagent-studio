"""Chain reader protocol and Web3 implementation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from avaxagent.core import create_web3

from app.chain.network import network

ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

EIP3009_AUTH_STATE_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "authorizer", "type": "address"},
            {"name": "nonce", "type": "bytes32"},
        ],
        "name": "authorizationState",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]


class ChainReader(Protocol):
    def native_balance(self, address: str) -> int: ...

    def erc20_balance(self, token: str, address: str) -> int: ...

    def block_number(self) -> int: ...

    def get_logs(
        self,
        address: str | list[str],
        topics: list,
        from_block: int,
        to_block: int,
    ) -> list[dict[str, Any]]: ...

    def authorization_used(self, token: str, authorizer: str, nonce: bytes) -> bool: ...


class Web3ChainReader:
    def __init__(self, rpc_url: str) -> None:
        self.w3 = create_web3(rpc_url)

    def native_balance(self, address: str) -> int:
        return self.w3.eth.get_balance(self.w3.to_checksum_address(address))

    def erc20_balance(self, token: str, address: str) -> int:
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token),
            abi=ERC20_BALANCE_ABI,
        )
        return int(contract.functions.balanceOf(self.w3.to_checksum_address(address)).call())

    def block_number(self) -> int:
        return int(self.w3.eth.block_number)

    def get_logs(
        self,
        address: str | list[str],
        topics: list,
        from_block: int,
        to_block: int,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": topics,
        }
        if isinstance(address, list):
            params["address"] = [self.w3.to_checksum_address(a) for a in address]
        else:
            params["address"] = self.w3.to_checksum_address(address)
        return list(self.w3.eth.get_logs(params))

    def authorization_used(self, token: str, authorizer: str, nonce: bytes) -> bool:
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token),
            abi=EIP3009_AUTH_STATE_ABI,
        )
        return bool(
            contract.functions.authorizationState(
                self.w3.to_checksum_address(authorizer),
                nonce,
            ).call()
        )


@lru_cache
def get_chain_reader() -> ChainReader:
    return Web3ChainReader(network().rpc_url)

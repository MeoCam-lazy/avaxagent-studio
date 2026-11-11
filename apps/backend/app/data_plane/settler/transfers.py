"""ERC-20 transfers out of agent wallets, shared by payouts and the fee sweep."""

from __future__ import annotations

from typing import Protocol

from avaxagent import TransactionPendingError
from avaxagent.core import create_web3
from avaxagent.erc20 import MinimalERC20Client
from web3 import Web3
from web3.exceptions import TransactionNotFound

from app.chain.network import network
from app.chain.signers import agent_signer
from app.control_plane.wallets.models import Wallet

# The SDK pads both the gas estimate and the gas price by 20% when it sends.
_SEND_BUFFER = 1.2


class TransferPending(Exception):
    """The transfer was broadcast but has no receipt yet; reconcile by hash."""

    def __init__(self, tx_hash: str) -> None:
        super().__init__(tx_hash)
        self.tx_hash = tx_hash


class TokenSender(Protocol):
    def transfer(self, wallet: Wallet, token: str, to: str, amount: int) -> str:
        """Send and wait for a successful receipt; return the tx hash.

        Raises ``TransferPending`` if broadcast without a receipt, any other
        exception if the transfer was not sent or reverted.
        """
        ...

    def receipt_status(self, tx_hash: str) -> int | None:
        """1 = success, 0 = reverted, None = no receipt yet."""
        ...

    def estimate_gas_cost_wei(self, wallet: Wallet, token: str, to: str, amount: int) -> int:
        """AVAX (wei) the wallet must hold for this transfer to be accepted."""
        ...


def _hex(value: object) -> str:
    text = value.hex() if hasattr(value, "hex") else str(value)
    return text if text.startswith("0x") else "0x" + text


class Erc20TokenSender:
    """ERC-20 ``transfer`` signed by the agent's Turnkey wallet (gas in AVAX)."""

    def __init__(self) -> None:
        self.w3 = create_web3(network().rpc_url)

    def transfer(self, wallet: Wallet, token: str, to: str, amount: int) -> str:
        client = MinimalERC20Client(self.w3, token, agent_signer(wallet))
        try:
            result = client.transfer(to, amount)
        except TransactionPendingError as exc:
            raise TransferPending(exc.tx_hash) from exc
        return _hex(result["transactionHash"])

    def receipt_status(self, tx_hash: str) -> int | None:
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return None
        return int(receipt["status"])

    def estimate_gas_cost_wei(self, wallet: Wallet, token: str, to: str, amount: int) -> int:
        client = MinimalERC20Client(self.w3, token)
        fn = client.contract.functions.transfer(Web3.to_checksum_address(to), amount)
        gas = fn.estimate_gas({"from": Web3.to_checksum_address(wallet.address)})
        return int(gas * _SEND_BUFFER) * int(self.w3.eth.gas_price * _SEND_BUFFER)

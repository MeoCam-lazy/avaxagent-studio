from __future__ import annotations

from typing import Any

import eth_account
from eth_account.signers.local import LocalAccount

from app.chain.reader import ChainReader
from app.control_plane.wallets.schemas import WalletPolicy
from app.control_plane.wallets.turnkey_admin import SubOrg, TurnkeyAdmin


class FakeTurnkeyAdmin(TurnkeyAdmin):
    def __init__(self) -> None:
        self.sub_orgs: dict[str, SubOrg] = {}
        self.keys: dict[str, LocalAccount] = {}
        self.policies: dict[str, WalletPolicy] = {}
        self._counter = 0

    async def create_agent_sub_org(self, name: str) -> SubOrg:
        self._counter += 1
        priv_key = f"0x{self._counter:064x}"
        account = eth_account.Account.from_key(priv_key)
        sub_org_id = f"sub-org-{self._counter}"
        wallet_id = f"wallet-{self._counter}"
        address = account.address
        sub_org = SubOrg(sub_org_id=sub_org_id, wallet_id=wallet_id, address=address)
        self.sub_orgs[sub_org_id] = sub_org
        self.keys[address.lower()] = account
        return sub_org

    async def set_policy(
        self,
        sub_org_id: str,
        policy: WalletPolicy,
        *,
        chain_id: int,
        allowed_eip712_contracts: list[str],
    ) -> str:
        self.policies[sub_org_id] = policy
        return f"policy-{sub_org_id}"


class FakeChainReader(ChainReader):
    def __init__(
        self,
        native_balance: int = 1_000_000_000_000_000_000,
        erc20_balance: int = 100_000_000,
        block_number: int = 123456,
    ) -> None:
        self._native_balance = native_balance
        self._erc20_balance = erc20_balance
        self._block_number = block_number
        self.used_authorizations: set[tuple[str, str, bytes]] = set()
        self.logs: list[dict[str, Any]] = []
        self.log_calls: list[dict[str, Any]] = []

    def set_block_number(self, n: int) -> None:
        self._block_number = n

    def native_balance(self, address: str) -> int:
        return self._native_balance

    def erc20_balance(self, token: str, address: str) -> int:
        return self._erc20_balance

    def block_number(self) -> int:
        return self._block_number

    def get_logs(
        self,
        address: str | list[str],
        topics: list,
        from_block: int,
        to_block: int,
    ) -> list[dict[str, Any]]:
        self.log_calls.append(
            {
                "address": address,
                "topics": topics,
                "from_block": from_block,
                "to_block": to_block,
            }
        )
        return self.logs

    def authorization_used(self, token: str, authorizer: str, nonce: bytes) -> bool:
        return (token.lower(), authorizer.lower(), nonce) in self.used_authorizations


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple, dict]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.enqueued.append((function, args, kwargs))


class FakeRelayer:
    def __init__(self, tx_hash: str = "0x" + "aa" * 32, should_fail: bool = False) -> None:
        self.tx_hash = tx_hash
        self.should_fail = should_fail
        self.calls: list[tuple[str, Any, str]] = []

    def settle(self, token: str, auth: Any, signature: str) -> str:
        self.calls.append((token, auth, signature))
        if self.should_fail:
            raise RuntimeError("settlement reverted")
        return self.tx_hash

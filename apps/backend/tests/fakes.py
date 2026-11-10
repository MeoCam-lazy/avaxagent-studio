from __future__ import annotations

import eth_account
from eth_account.signers.local import LocalAccount

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

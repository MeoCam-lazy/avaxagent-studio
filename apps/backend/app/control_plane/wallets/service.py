"""Turnkey sub-org provisioning + policy management.

Flow for ``provision``:
1. Create a Turnkey sub-organization under the studio's parent org
   (``TURNKEY_ORGANIZATION_ID``) with a non-root API user for the agent.
2. Create an Ethereum wallet account in the sub-org -> agent address.
3. Install an ALLOW policy derived from ``WalletPolicy`` (root keys bypass
   policies, so the agent must never use a root key).
4. Persist ``Wallet`` and link it to the agent; build signers at runtime with
   ``avaxagent.wallets.TurnkeyWalletProvider(..., expected_chain_id=chain_id())``.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain import network as net
from app.chain.reader import ChainReader, get_chain_reader
from app.control_plane.agents.models import AgentStatus
from app.control_plane.agents.service import AgentService
from app.control_plane.wallets.models import Wallet
from app.control_plane.wallets.schemas import WalletBalances, WalletPolicy, WalletRead
from app.control_plane.wallets.turnkey_admin import TurnkeyAdmin, get_turnkey_admin
from app.core.config import settings


class WalletService:
    def __init__(
        self,
        session: AsyncSession,
        admin: TurnkeyAdmin | None = None,
        reader: ChainReader | None = None,
    ) -> None:
        self.session = session
        self.admin = admin or get_turnkey_admin()
        self.reader = reader or get_chain_reader()

    async def provision(self, owner_id: str, agent_id: uuid.UUID) -> WalletRead:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.wallet_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "wallet_exists"},
            )
        if agent.status != AgentStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "agent_not_in_draft"},
            )

        sub_org = await self.admin.create_agent_sub_org(agent.name or agent.slug)
        default_policy = WalletPolicy()
        await self.admin.set_policy(
            sub_org.sub_org_id,
            default_policy,
            chain_id=net.chain_id(),
            allowed_eip712_contracts=[net.payment_asset_address()],
        )

        wallet = Wallet(
            provider="turnkey",
            turnkey_sub_org_id=sub_org.sub_org_id,
            turnkey_wallet_id=sub_org.wallet_id,
            address=sub_org.address,
            chain_id=net.chain_id(),
            policy=default_policy.model_dump(),
        )
        self.session.add(wallet)
        await self.session.flush()

        agent.wallet_id = wallet.id
        agent.status = AgentStatus.PROVISIONING
        await self.session.commit()

        return WalletRead.model_validate(wallet)

    async def get(self, owner_id: str, agent_id: uuid.UUID) -> WalletRead:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.wallet_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )
        wallet = (
            await self.session.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )
        return WalletRead.model_validate(wallet)

    async def update_policy(
        self, owner_id: str, agent_id: uuid.UUID, policy: WalletPolicy
    ) -> WalletRead:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.wallet_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )
        wallet = (
            await self.session.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )

        if wallet.turnkey_sub_org_id:
            await self.admin.set_policy(
                wallet.turnkey_sub_org_id,
                policy,
                chain_id=wallet.chain_id,
                allowed_eip712_contracts=[net.payment_asset_address()],
            )

        wallet.policy = policy.model_dump()
        await self.session.commit()
        return WalletRead.model_validate(wallet)

    async def balances(self, owner_id: str, agent_id: uuid.UUID) -> WalletBalances:
        agent = await AgentService(self.session).get_owned(owner_id, agent_id)
        if agent.wallet_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )
        wallet = (
            await self.session.execute(select(Wallet).where(Wallet.id == agent.wallet_id))
        ).scalar_one_or_none()
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "wallet_not_found"},
            )

        native = self.reader.native_balance(wallet.address)
        erc20 = self.reader.erc20_balance(net.payment_asset_address(), wallet.address)

        return WalletBalances(
            address=wallet.address,
            chain_id=wallet.chain_id,
            avax_wei=native,
            payment_asset=settings.payment_asset,
            payment_asset_atomic=erc20,
        )

"""Event streams the indexer follows on Avalanche C-Chain."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.chain import network as net
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.ledger import record_income
from app.control_plane.jobs.models import Job
from app.control_plane.wallets.models import Wallet
from app.core.config import settings

log = logging.getLogger(__name__)

IDENTITY_REGISTRY_EVENTS_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "agentId", "type": "uint256"},
            {"indexed": False, "name": "agentURI", "type": "string"},
            {"indexed": True, "name": "owner", "type": "address"},
        ],
        "name": "Registered",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "agentId", "type": "uint256"},
            {"indexed": False, "name": "newURI", "type": "string"},
            {"indexed": True, "name": "updatedBy", "type": "address"},
        ],
        "name": "URIUpdated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]

ERC20_TRANSFER_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
]

_w3 = Web3()
_id_contract = _w3.eth.contract(abi=IDENTITY_REGISTRY_EVENTS_ABI)
_erc20_contract = _w3.eth.contract(abi=ERC20_TRANSFER_EVENT_ABI)


@dataclass
class Stream:
    name: str
    description: str
    enabled: bool = True

    async def address(self, db: AsyncSession) -> list[str] | str:
        return []

    async def topics(self, db: AsyncSession) -> list:
        return []

    async def handle(self, db: AsyncSession, logs: list[dict[str, Any]]) -> None:
        pass


class IdentityStream(Stream):
    def __init__(self) -> None:
        super().__init__(
            name="erc8004.identity",
            description=(
                "IdentityRegistry Registered/Transfer/URIUpdated for managed agents "
                "(confirms registrations, detects ownership changes)"
            ),
            enabled=True,
        )

    async def address(self, db: AsyncSession) -> list[str]:
        return [net.identity_registry()]

    async def handle(self, db: AsyncSession, logs: list[dict[str, Any]]) -> None:
        for log_entry in logs:
            # 1. Registered event
            try:
                event_data = _id_contract.events.Registered().process_log(log_entry)
                args = event_data["args"]
                owner = args["owner"]
                agent_id = args["agentId"]
                agent_uri = args["agentURI"]

                stmt = (
                    select(Agent)
                    .join(Wallet, Agent.wallet_id == Wallet.id)
                    .where(func.lower(Wallet.address) == owner.lower())
                )
                agent = (await db.execute(stmt)).scalar_one_or_none()
                if agent:
                    agent.erc8004_agent_id = agent_id
                    agent.agent_uri = agent_uri
                    agent.status = AgentStatus.ACTIVE
                continue
            except Exception:
                pass

            # 2. URIUpdated event
            try:
                event_data = _id_contract.events.URIUpdated().process_log(log_entry)
                args = event_data["args"]
                agent_id = args["agentId"]
                new_uri = args["newURI"]

                stmt = select(Agent).where(Agent.erc8004_agent_id == agent_id)
                agent = (await db.execute(stmt)).scalar_one_or_none()
                if agent:
                    agent.agent_uri = new_uri
                continue
            except Exception:
                pass

            # 3. Transfer event
            try:
                event_data = _id_contract.events.Transfer().process_log(log_entry)
                args = event_data["args"]
                from_addr = args["from"]
                to_addr = args["to"]
                token_id = args["tokenId"]

                if from_addr and from_addr.lower() != "0x0000000000000000000000000000000000000000":
                    stmt = (
                        select(Agent)
                        .join(Wallet, Agent.wallet_id == Wallet.id)
                        .where(
                            func.lower(Wallet.address) == from_addr.lower(),
                            Agent.erc8004_agent_id == token_id,
                        )
                    )
                    agent = (await db.execute(stmt)).scalar_one_or_none()
                    if agent:
                        agent.status = AgentStatus.PAUSED
                        log.warning(
                            "Agent %s token %d transferred from wallet %s to %s; pausing agent",
                            agent.slug,
                            token_id,
                            from_addr,
                            to_addr,
                        )
            except Exception:
                pass

        await db.flush()


class IncomeStream(Stream):
    def __init__(self) -> None:
        super().__init__(
            name="x402.income",
            description="Payment-asset (USDC) Transfer events into agent wallets -> ledger INCOME",
            enabled=True,
        )

    async def address(self, db: AsyncSession) -> list[str]:
        return [net.payment_asset_address()]

    async def handle(self, db: AsyncSession, logs: list[dict[str, Any]]) -> None:
        for log_entry in logs:
            try:
                event_data = _erc20_contract.events.Transfer().process_log(log_entry)
            except Exception:
                continue

            args = event_data["args"]
            to_addr = args["to"]
            value = int(args["value"])

            stmt = (
                select(Agent, Wallet)
                .join(Wallet, Agent.wallet_id == Wallet.id)
                .where(func.lower(Wallet.address) == to_addr.lower())
            )
            row = (await db.execute(stmt)).first()
            if not row:
                continue

            agent, _wallet = row
            raw_tx = log_entry.get("transactionHash")
            tx_hash = raw_tx.hex() if hasattr(raw_tx, "hex") else str(raw_tx)
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash

            log_index = int(log_entry.get("logIndex", 0))

            job_stmt = select(Job).where(Job.payment_tx_hash == tx_hash)
            job = (await db.execute(job_stmt)).scalar_one_or_none()

            asset = net.payment_asset_address()
            if job is not None:
                await record_income(
                    db,
                    job=job,
                    amount=value,
                    asset=asset,
                    tx_hash=tx_hash,
                    log_index=log_index,
                )
            else:
                try:
                    async with db.begin_nested():
                        await record_income(
                            db,
                            agent_id=agent.id,
                            chain_id=agent.chain_id,
                            amount=value,
                            asset=asset,
                            tx_hash=tx_hash,
                            log_index=log_index,
                        )
                except IntegrityError:
                    pass

        await db.flush()


def streams() -> list[Stream]:
    return [
        IdentityStream(),
        IncomeStream(),
        Stream(
            "erc8183.jobs",
            "AgenticCommerce JobFunded for managed providers -> enqueue RUN_JOB "
            "(only with the studio-deployed ERC-8183 stack)",
            settings.commerce_enabled,
        ),
    ]

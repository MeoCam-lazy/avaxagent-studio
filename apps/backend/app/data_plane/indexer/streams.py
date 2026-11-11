"""Event streams the indexer follows on Avalanche C-Chain."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.chain import commerce
from app.chain import network as net
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.billing.ledger import record_income
from app.control_plane.jobs.events import add_event
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.wallets.models import Wallet
from app.core.config import SettlementMode, settings
from app.core.queue import RUN_JOB, get_queue

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

JOB_FUNDED_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "jobId", "type": "uint256"},
            {"indexed": True, "name": "client", "type": "address"},
            {"indexed": True, "name": "provider", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "JobFunded",
        "type": "event",
    }
]

JOB_FUNDED_TOPIC = "0x" + Web3.keccak(
    text="JobFunded(uint256,address,address,uint256)"
).hex().removeprefix("0x")

_w3 = Web3()
_id_contract = _w3.eth.contract(abi=IDENTITY_REGISTRY_EVENTS_ABI)
_erc20_contract = _w3.eth.contract(abi=ERC20_TRANSFER_EVENT_ABI)
_commerce_contract = _w3.eth.contract(abi=JOB_FUNDED_EVENT_ABI)


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

            job_stmt = select(Job).where(
                or_(Job.payment_tx_hash == tx_hash, Job.settle_tx_hash == tx_hash)
            )
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


class EscrowJobStream(Stream):
    """Watches ``AgenticCommerce.JobFunded`` and enqueues ``RUN_JOB`` for managed agents."""

    def __init__(
        self,
        *,
        queue: Any | None = None,
        commerce_reader: Any | None = None,
    ) -> None:
        super().__init__(
            name="erc8183.jobs",
            description=(
                "AgenticCommerce JobFunded for managed providers -> enqueue RUN_JOB "
                "(only with the studio-deployed ERC-8183 stack)"
            ),
            enabled=settings.commerce_enabled,
        )
        self.queue = queue
        self.commerce_reader = commerce_reader

    async def address(self, db: AsyncSession) -> list[str]:
        return [commerce.contracts().commerce]

    async def topics(self, db: AsyncSession) -> list:
        return [JOB_FUNDED_TOPIC]

    async def handle(self, db: AsyncSession, logs: list[dict[str, Any]]) -> None:
        enqueued_ids: list[str] = []

        for log_entry in logs:
            try:
                event_data = _commerce_contract.events.JobFunded().process_log(log_entry)
            except Exception:
                continue

            args = event_data["args"]
            chain_job_id = int(args["jobId"])
            client_addr = str(args["client"])
            provider_addr = str(args["provider"])
            amount = int(args["amount"])

            stmt = (
                select(Agent, Wallet)
                .join(Wallet, Agent.wallet_id == Wallet.id)
                .where(
                    func.lower(Wallet.address) == provider_addr.lower(),
                    Agent.deleted_at.is_(None),
                )
            )
            row = (await db.execute(stmt)).first()
            if not row:
                continue

            agent, _wallet = row
            raw_tx = log_entry.get("transactionHash")
            tx_hash = raw_tx.hex() if hasattr(raw_tx, "hex") else str(raw_tx)
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash

            request_payload: dict[str, Any] = {"chain_job_id": chain_job_id}
            reader = self.commerce_reader
            if reader is not None:
                try:
                    info = await asyncio.to_thread(reader.get_job, chain_job_id)
                    desc = info.get("description")
                    if desc:
                        request_payload = {"message": desc, "chain_job_id": chain_job_id}
                except Exception:
                    log.warning("Failed to fetch description for chain_job_id=%d", chain_job_id)

            try:
                async with db.begin_nested():
                    job = Job(
                        agent_id=agent.id,
                        settlement_mode=SettlementMode.ERC8183,
                        status=JobStatus.FUNDED,
                        chain_id=agent.chain_id,
                        chain_job_id=chain_job_id,
                        client_address=client_addr,
                        amount_atomic=amount,
                        asset=net.payment_asset_address(),
                        payment_tx_hash=tx_hash,
                        request=request_payload,
                    )
                    db.add(job)
                    await db.flush()
                    await add_event(db, job, "funded", tx_hash=tx_hash, chain_job_id=chain_job_id)
                    enqueued_ids.append(str(job.id))
            except IntegrityError:
                continue

        await db.flush()

        if enqueued_ids:
            q = self.queue
            owns_queue = q is None
            if q is None:
                q = await get_queue()
            try:
                for jid in enqueued_ids:
                    await q.enqueue_job(RUN_JOB, jid)
            finally:
                if owns_queue and hasattr(q, "aclose"):
                    await q.aclose()


def streams() -> list[Stream]:
    return [
        IdentityStream(),
        IncomeStream(),
        EscrowJobStream(),
    ]

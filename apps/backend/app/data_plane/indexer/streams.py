"""Event streams the indexer follows on Avalanche C-Chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


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


def streams() -> list[Stream]:
    return [
        Stream(
            "erc8004.identity",
            "IdentityRegistry Registered/Transfer/URIUpdated for managed agents "
            "(confirms registrations, detects ownership changes)",
            True,
        ),
        Stream(
            "x402.income",
            "Payment-asset (USDC) Transfer events into agent wallets -> ledger INCOME",
            True,
        ),
        Stream(
            "erc8183.jobs",
            "AgenticCommerce JobFunded for managed providers -> enqueue RUN_JOB "
            "(only with the studio-deployed ERC-8183 stack)",
            settings.commerce_enabled,
        ),
    ]

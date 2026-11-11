"""Agent config persistence with SQLAlchemy queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chain.network import chain_id
from app.control_plane.agents.models import Agent, AgentStatus
from app.control_plane.agents.schemas import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
    LLMConfig,
    MarketplaceAgent,
    MarketplaceAgentProfile,
)
from app.control_plane.jobs.models import Job, JobStatus
from app.control_plane.wallets.models import Wallet
from app.core.config import settings


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_read(self, agent: Agent, wallet_address: str | None = None) -> AgentRead:
        llm_cfg = (
            LLMConfig(**agent.llm_config)
            if isinstance(agent.llm_config, dict)
            else agent.llm_config
        )
        return AgentRead(
            id=agent.id,
            slug=agent.slug,
            name=agent.name,
            description=agent.description,
            status=agent.status,
            is_public=agent.is_public,
            llm_config=llm_cfg,
            skills=agent.skills,
            settlement_mode=agent.settlement_mode,
            price_atomic=agent.price_atomic,
            chain_id=agent.chain_id,
            erc8004_agent_id=agent.erc8004_agent_id,
            agent_uri=agent.agent_uri,
            wallet_address=wallet_address,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    async def create(self, owner_id: str, data: AgentCreate) -> AgentRead:
        """Insert a DRAFT agent on the configured chain (no wallet/identity yet)."""
        agent = Agent(
            owner_id=owner_id.lower(),
            slug=data.slug,
            name=data.name,
            description=data.description,
            status=AgentStatus.DRAFT,
            is_public=data.is_public,
            llm_config=data.llm_config.model_dump(),
            skills=data.skills,
            settlement_mode=data.settlement_mode,
            price_atomic=data.price_atomic,
            chain_id=chain_id(),
        )
        self.session.add(agent)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if "slug" in str(exc).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "slug_taken"},
                ) from None
            raise
        await self.session.refresh(agent)
        return self._to_read(agent)

    async def get_owned(self, owner_id: str, agent_id: uuid.UUID) -> Agent:
        """Fetch the ORM row if owned by owner_id and not deleted; raise 404 otherwise."""
        stmt = select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == owner_id.lower(),
            Agent.deleted_at.is_(None),
        )
        agent = (await self.session.execute(stmt)).scalar_one_or_none()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "agent_not_found"},
            )
        return agent

    async def get_by_slug(self, slug: str) -> Agent | None:
        """Fetch active, non-deleted agent by slug for gateway consumption."""
        stmt = select(Agent).where(
            Agent.slug == slug,
            Agent.status == AgentStatus.ACTIVE,
            Agent.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_owner(self, owner_id: str) -> list[AgentRead]:
        stmt = (
            select(Agent, Wallet.address.label("wallet_address"))
            .outerjoin(Wallet, Agent.wallet_id == Wallet.id)
            .where(
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
            .order_by(Agent.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [self._to_read(agent, wallet_address) for agent, wallet_address in rows]

    async def get(self, owner_id: str, agent_id: uuid.UUID) -> AgentRead:
        stmt = (
            select(Agent, Wallet.address.label("wallet_address"))
            .outerjoin(Wallet, Agent.wallet_id == Wallet.id)
            .where(
                Agent.id == agent_id,
                Agent.owner_id == owner_id.lower(),
                Agent.deleted_at.is_(None),
            )
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "agent_not_found"},
            )
        agent, wallet_address = row
        return self._to_read(agent, wallet_address)

    async def update(self, owner_id: str, agent_id: uuid.UUID, data: AgentUpdate) -> AgentRead:
        """Patch config; changing public profile fields should refresh the agent URI."""
        agent = await self.get_owned(owner_id, agent_id)
        updates = data.model_dump(exclude_unset=True)
        for k, v in updates.items():
            if k == "llm_config" and v is not None:
                setattr(agent, k, v if isinstance(v, dict) else v.model_dump())
            else:
                setattr(agent, k, v)
        await self.session.commit()
        await self.session.refresh(agent)

        wallet_address = None
        if agent.wallet_id:
            wallet_res = await self.session.execute(
                select(Wallet.address).where(Wallet.id == agent.wallet_id)
            )
            wallet_address = wallet_res.scalar_one_or_none()
        return self._to_read(agent, wallet_address)

    async def delete(self, owner_id: str, agent_id: uuid.UUID) -> None:
        """Soft-delete / pause. The ERC-8004 token itself cannot be burned by the studio."""
        agent = await self.get_owned(owner_id, agent_id)
        agent.deleted_at = datetime.now(timezone.utc)
        agent.status = AgentStatus.PAUSED
        await self.session.commit()

    async def marketplace(self, q: str | None, limit: int, offset: int) -> list[MarketplaceAgent]:
        """Public ACTIVE agents; may later merge 8004scan results for Avalanche."""
        stmt = select(Agent).where(*self._listed())
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Agent.name.ilike(pattern),
                    Agent.description.ilike(pattern),
                    cast(Agent.skills, String).ilike(pattern),
                )
            )
        stmt = stmt.order_by(Agent.created_at.desc()).limit(limit).offset(offset)
        agents = (await self.session.execute(stmt)).scalars().all()
        return [MarketplaceAgent(**self._public_fields(a)) for a in agents]

    async def marketplace_profile(self, slug: str) -> MarketplaceAgentProfile:
        """One listed agent, by slug. Unlisted agents are 404 like missing ones."""
        stmt = select(Agent).where(Agent.slug == slug, *self._listed())
        agent = (await self.session.execute(stmt)).scalar_one_or_none()
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"error": "agent_not_found"}
            )
        completed = await self.session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.agent_id == agent.id, Job.status == JobStatus.SETTLED)
        )
        return MarketplaceAgentProfile(
            **self._public_fields(agent),
            created_at=agent.created_at,
            jobs_completed=completed or 0,
        )

    @staticmethod
    def _listed() -> tuple[Any, ...]:
        return (
            Agent.is_public.is_(True),
            Agent.status == AgentStatus.ACTIVE,
            Agent.deleted_at.is_(None),
        )

    @staticmethod
    def _public_fields(a: Agent) -> dict[str, Any]:
        base = f"{settings.public_gateway_url}/agents/{a.slug}"
        return {
            "slug": a.slug,
            "name": a.name,
            "description": a.description,
            "skills": a.skills,
            "settlement_mode": a.settlement_mode,
            "price_atomic": a.price_atomic,
            "chain_id": a.chain_id,
            "erc8004_agent_id": a.erc8004_agent_id,
            "agent_card_url": f"{base}/.well-known/agent-card.json",
            "a2a_url": f"{base}/a2a",
        }

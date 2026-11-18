from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.control_plane.agents.schemas import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
    MarketplaceAgent,
    MarketplaceAgentProfile,
)
from app.control_plane.agents.service import AgentService
from app.core.config import settings
from app.core.errors import FeatureDisabled
from app.core.security import CurrentUser
from app.data_plane.workers.llm import get_llm_providers, list_provider_models
from app.db.session import DbSession

router = APIRouter(prefix="/agents", tags=["agents"])
marketplace_router = APIRouter(prefix="/marketplace", tags=["marketplace"])
logger = logging.getLogger(__name__)


class LLMProvidersRead(BaseModel):
    default_provider: str
    default_model: str
    providers: list[str]


@router.get("/llm/providers", response_model=LLMProvidersRead)
async def llm_providers(user: CurrentUser) -> LLMProvidersRead:
    del user
    providers = get_llm_providers()
    default_provider = settings.llm_provider if settings.llm_provider in providers else (
        providers[0] if providers else settings.llm_provider
    )
    return LLMProvidersRead(
        default_provider=default_provider,
        default_model=settings.llm_model,
        providers=providers,
    )


@router.get("/llm/models", response_model=list[str])
async def llm_models(
    user: CurrentUser, provider: str = Query(pattern="^(openai|anthropic)$")
) -> list[str]:
    del user
    try:
        return await list_provider_models(provider)
    except FeatureDisabled as exc:
        raise HTTPException(status_code=503, detail={"error": "llm_provider_unavailable"}) from exc
    except Exception as exc:
        logger.exception("Failed to list models for provider %s", provider)
        raise HTTPException(status_code=502, detail={"error": "llm_model_list_failed"}) from exc


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, user: CurrentUser, db: DbSession) -> AgentRead:
    return await AgentService(db).create(user.id, body)


@router.get("", response_model=list[AgentRead])
async def list_agents(user: CurrentUser, db: DbSession) -> list[AgentRead]:
    return await AgentService(db).list_for_owner(user.id)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(agent_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AgentRead:
    return await AgentService(db).get(user.id, agent_id)


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID, body: AgentUpdate, user: CurrentUser, db: DbSession
) -> AgentRead:
    return await AgentService(db).update(user.id, agent_id, body)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await AgentService(db).delete(user.id, agent_id)


@marketplace_router.get("/agents", response_model=list[MarketplaceAgent])
async def marketplace_agents(
    db: DbSession,
    q: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
) -> list[MarketplaceAgent]:
    return await AgentService(db).marketplace(q, limit, offset)


@marketplace_router.get("/agents/{slug}", response_model=MarketplaceAgentProfile)
async def marketplace_agent(slug: str, db: DbSession) -> MarketplaceAgentProfile:
    return await AgentService(db).marketplace_profile(slug)

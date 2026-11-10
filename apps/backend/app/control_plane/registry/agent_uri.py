"""ERC-8004 Agent URI building and metadata uploading."""

from __future__ import annotations

from avaxagent.erc8004.agent_uri import AgentURIGenerator
from avaxagent.erc8004.models import AgentEndpoint
from avaxagent.storage.sync_utils import upload_sync

from app.control_plane.agents.models import Agent
from app.core.config import settings
from app.data_plane.storage.service import get_storage


def build_agent_uri(agent: Agent) -> str:
    name = agent.name or "Agent"
    description = agent.description or agent.name or "AI Agent"
    endpoint_url = (
        f"{settings.public_gateway_url}/agents/{agent.slug}/.well-known/agent-card.json"
    )
    endpoints = [AgentEndpoint(name="A2A", endpoint=endpoint_url, version="0.3.0")]
    data_uri = AgentURIGenerator.generate_agent_uri(
        name=name,
        description=description,
        endpoints=endpoints,
    )
    if settings.storage_backend.lower() != "local":
        reg_file = AgentURIGenerator.generate_registration_file(
            name=name,
            description=description,
            endpoints=endpoints,
        )
        storage = get_storage()
        return upload_sync(storage, reg_file, filename=f"agent-{agent.slug}.json")
    return data_uri

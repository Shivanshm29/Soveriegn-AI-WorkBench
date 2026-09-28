"""Diagnostic snapshot schema and aggregator."""

from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.config.settings import get_settings


class RegistrySnapshot(BaseModel):
    """Diagnostic snapshot of all active registries and sovereignty status."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sovereign_mode: bool = True
    model_count: int
    agent_count: int
    tool_count: int
    models: List[str]
    agents: List[str]
    tools: List[str]
    agent_capabilities: Dict[str, List[str]] = Field(default_factory=dict)
    tool_capabilities: Dict[str, List[str]] = Field(default_factory=dict)


def get_registry_snapshot(
    model_registry: ModelRegistry,
    agent_registry: AgentRegistry,
    tool_registry: ToolRegistry,
) -> RegistrySnapshot:
    """Produce an instantaneous diagnostic snapshot across all 3 authoritative registries."""
    settings = get_settings()

    agents = agent_registry.list()
    tools = tool_registry.list()
    models = model_registry.list()

    agent_caps = {a.agent_id: a.capabilities for a in agents}
    tool_caps = {t.tool_id: t.capabilities for t in tools}

    return RegistrySnapshot(
        sovereign_mode=settings.SOVEREIGN_MODE,
        model_count=len(models),
        agent_count=len(agents),
        tool_count=len(tools),
        models=[getattr(m, "id", getattr(m, "model_id", str(m))) for m in models],
        agents=[a.agent_id for a in agents],
        tools=[t.tool_id for t in tools],
        agent_capabilities=agent_caps,
        tool_capabilities=tool_caps,
    )

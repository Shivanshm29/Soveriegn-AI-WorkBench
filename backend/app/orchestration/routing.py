"""Capability-based routing for agents and models."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from backend.app.agents.registry import AgentRegistry
from backend.app.models.registry import ModelRegistry
from backend.app.orchestration.errors import RoutingError


@dataclass
class RoutingDecision:
    """Structured routing outcome mapping capabilities to agents and models."""

    selected_agents: Dict[str, str] = field(default_factory=dict)
    selected_models: Dict[str, str] = field(default_factory=dict)
    candidate_agents: Dict[str, List[str]] = field(default_factory=dict)
    unroutable_capabilities: List[str] = field(default_factory=list)

    @property
    def is_routable(self) -> bool:
        """Check if all capabilities were successfully routed."""
        return len(self.unroutable_capabilities) == 0


class TaskRouter:
    """Capability-based router coordinating with AgentRegistry and ModelRegistry."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        model_registry: ModelRegistry,
    ):
        self.agent_registry = agent_registry
        self.model_registry = model_registry

    def route(
        self,
        capabilities: List[str],
        modalities: Optional[List[str]] = None,
    ) -> RoutingDecision:
        """Route capabilities to registered agents and models."""
        decision = RoutingDecision()

        if not capabilities:
            # Default to reasoning capability if none specified
            capabilities = ["reasoning"]

        # 1. Capability-based agent routing
        for cap in capabilities:
            candidates = self.agent_registry.find_by_capability(cap)
            if candidates:
                # Pick the first enabled agent
                decision.selected_agents[cap] = candidates[0].agent_id
                decision.candidate_agents[cap] = [c.agent_id for c in candidates]
            else:
                decision.unroutable_capabilities.append(cap)

        if decision.unroutable_capabilities:
            raise RoutingError(
                f"No registered agents found for required capabilities: {decision.unroutable_capabilities}"
            )

        # 2. Model resolution via ModelRegistry
        try:
            model_selection = self.model_registry.resolve(
                capabilities=capabilities,
                modalities=modalities,
            )
            decision.selected_models["primary"] = model_selection.selected_model_name
            decision.selected_models["model_id"] = model_selection.selected_model_id
        except Exception:
            # Fallback to general reasoning model
            general_def = self.model_registry.get_model_definition("general_reasoning")
            if general_def:
                decision.selected_models["primary"] = general_def.model_name
                decision.selected_models["model_id"] = general_def.id
            else:
                raise RoutingError("Failed to resolve a model from ModelRegistry.")

        return decision

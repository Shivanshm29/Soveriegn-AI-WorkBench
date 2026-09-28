"""Test C: Capability-Based Routing Node."""

import pytest
from backend.app.agents.registry import AgentRegistry
from backend.app.models.registry import ModelRegistry
from backend.app.orchestration.routing import TaskRouter
from backend.app.orchestration.errors import RoutingError


def test_capability_based_agent_routing():
    """Verify capabilities correctly route to standard registered agents."""
    router = TaskRouter(
        agent_registry=AgentRegistry(),
        model_registry=ModelRegistry(),
    )

    decision = router.route(
        capabilities=["visual_reasoning", "code_generation", "calculation"]
    )
    assert decision.is_routable
    assert decision.selected_agents["visual_reasoning"] == "vision_agent"
    assert decision.selected_agents["code_generation"] == "coding_agent"
    assert decision.selected_agents["calculation"] == "data_agent"
    assert "primary" in decision.selected_models


def test_unknown_capability_fails_cleanly():
    """Verify unroutable/unknown capabilities raise RoutingError."""
    router = TaskRouter(
        agent_registry=AgentRegistry(),
        model_registry=ModelRegistry(),
    )

    with pytest.raises(RoutingError) as exc_info:
        router.route(capabilities=["non_existent_specialized_magic_capability"])
    assert "No registered agents found" in str(exc_info.value)

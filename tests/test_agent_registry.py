"""Tests for AgentRegistry in Phase 3."""

import pytest
from backend.app.schemas.agents import AgentContract
from backend.app.agents.registry import (
    AgentRegistry,
    DuplicateAgentError,
    UnknownAgentError,
)


def test_agent_registry_prepopulated_defaults():
    """Verify that AgentRegistry pre-populates all 7 standard agents from AGENTS.md."""
    registry = AgentRegistry()
    expected_agents = [
        "main_agent",
        "reasoning_agent",
        "document_agent",
        "vision_agent",
        "knowledge_agent",
        "coding_agent",
        "data_agent",
    ]
    for agent_id in expected_agents:
        assert registry.exists(agent_id), f"Expected agent {agent_id} to be registered"
        agent = registry.get(agent_id)
        assert agent is not None
        assert agent.agent_id == agent_id
        assert len(agent.capabilities) > 0


def test_agent_registry_registration_and_retrieval():
    """Verify dynamic agent registration and retrieval."""
    registry = AgentRegistry(populate_defaults=False)
    agent = AgentContract(
        agent_id="custom_agent",
        description="Custom specialist agent",
        capabilities=["custom_capability"],
        risk_class="LOW",
    )
    registry.register(agent)

    assert registry.exists("custom_agent")
    assert registry.get("custom_agent") == agent
    assert registry.get_or_raise("custom_agent") == agent


def test_agent_registry_duplicate_rejection():
    """Verify duplicate agent registration raises DuplicateAgentError."""
    registry = AgentRegistry(populate_defaults=False)
    agent = AgentContract(
        agent_id="agent_1",
        description="First agent",
    )
    registry.register(agent)

    with pytest.raises(DuplicateAgentError):
        registry.register(agent)

    # Overwrite works when enabled
    agent_updated = AgentContract(
        agent_id="agent_1",
        description="Updated agent",
    )
    registry.register(agent_updated, overwrite=True)
    assert registry.get("agent_1").description == "Updated agent"


def test_agent_registry_unknown_agent_error():
    """Verify unknown agents raise UnknownAgentError when required."""
    registry = AgentRegistry(populate_defaults=False)
    assert registry.get("non-existent") is None
    assert not registry.exists("non-existent")

    with pytest.raises(UnknownAgentError):
        registry.get_or_raise("non-existent")

    with pytest.raises(UnknownAgentError):
        registry.unregister("non-existent")


def test_agent_registry_find_by_capability():
    """Verify capability-based agent discovery per AGENTS.md."""
    registry = AgentRegistry()

    # Visual reasoning
    vision_agents = registry.find_by_capability("visual_reasoning")
    assert any(a.agent_id == "vision_agent" for a in vision_agents)

    # Code generation
    coding_agents = registry.find_by_capability("code_generation")
    assert any(a.agent_id == "coding_agent" for a in coding_agents)

    # Planning
    planning_agents = registry.find_by_capability("planning")
    assert any(a.agent_id == "reasoning_agent" for a in planning_agents)

    # Non-existent capability
    none = registry.find_by_capability("unknown_cap")
    assert len(none) == 0


def test_agent_registry_find_by_tool():
    """Verify discovery of agents allowed to use a given tool."""
    registry = AgentRegistry()
    ocr_agents = registry.find_by_tool("ocr")
    agent_ids = [a.agent_id for a in ocr_agents]
    assert "document_agent" in agent_ids or "vision_agent" in agent_ids

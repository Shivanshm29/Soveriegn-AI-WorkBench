"""Tests for vision model routing, AgentRegistry, ToolRegistry, A2A messaging, and caching."""

import pytest
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.schemas.agents import A2AMessage
from backend.app.agents.a2a import A2AMessageValidator
from backend.app.vision.agent import EngineeringVisionAgent
from backend.app.vision.tools import get_vision_tools, register_vision_tools
from tests.fixtures.vision_fixtures import (
    create_drawing_with_dimensions,
    create_drawing_with_title_block,
)


def test_vision_model_resolution_no_hardcoding():
    """Section 5: Vision model must be selected dynamically through ModelRegistry without hardcoded IDs."""
    model_reg = ModelRegistry()
    agent = EngineeringVisionAgent(model_registry=model_reg)

    resolved_model = agent.resolve_vision_model()
    assert resolved_model is not None
    # Must resolve to one of the configured models in registry (e.g. Qwen/Qwen3-VL-4B-Instruct)
    model_cfg = model_reg.get(resolved_model)
    assert model_cfg is not None
    assert "visual_reasoning" in model_cfg.capabilities or "vision.engineering_analysis" in model_cfg.capabilities


def test_agent_registry_vision_agent_capabilities():
    """Verify vision_agent has the required engineering vision capabilities and tools in AgentRegistry."""
    agent_reg = AgentRegistry()
    vision_agent = agent_reg.get("vision_agent")

    assert vision_agent is not None
    assert vision_agent.enabled is True

    # Required capabilities
    expected_caps = [
        "vision.engineering_analysis",
        "vision.image_understanding",
        "engineering_drawing_observation",
        "engineering_drawing_analysis",
    ]
    for cap in expected_caps:
        assert cap in vision_agent.capabilities

    # Required tools
    expected_tools = [
        "engineering_drawing_analyze",
        "industrial_image_inspect",
        "image_preprocess_tile",
        "visual_region_detect",
        "verify_visual_evidence",
    ]
    for t in expected_tools:
        assert t in vision_agent.allowed_tools


def test_tool_registry_registration():
    """Verify registration of Phase 7 vision tools into ToolRegistry."""
    tool_reg = ToolRegistry()
    register_vision_tools(tool_reg)

    for tool_def in get_vision_tools():
        assert tool_reg.exists(tool_def.tool_id)
        registered = tool_reg.get(tool_def.tool_id)
        assert registered.enabled is True
        assert registered.risk_level == "LOW"
        assert registered.requires_approval is False


def test_a2a_vision_delegation_message_validation():
    """Verify structured A2A message contract for vision task delegation."""
    agent_reg = AgentRegistry()
    msg = A2AMessage(
        message_id="msg_vision_001",
        task_id="task_vis_001",
        sender="main_agent",
        receiver="vision_agent",
        type="TASK_DELEGATION",
        payload={
            "action": "Analyze engineering drawing for dimensions and title block",
            "capability": "vision.engineering_analysis",
            "required_tools": ["engineering_drawing_analyze"],
        },
        requested_capabilities=["vision.engineering_analysis"],
        status="PENDING",
    )

    # Validates cleanly against AgentRegistry
    A2AMessageValidator.validate(msg, agent_registry=agent_reg)


def test_vision_caching_behavior(tmp_path):
    """Verify local hash-based caching reuses results for identical source_hash."""
    img_path = str(tmp_path / "dwg_cache.png")
    create_drawing_with_dimensions(img_path)

    agent = EngineeringVisionAgent()

    # First call - cache miss
    res1 = agent.process_image(img_path, task_id="task_1")
    assert len(agent._cache) == 1

    # Second call - cache hit
    res2 = agent.process_image(img_path, task_id="task_2")
    assert res2.source_hash == res1.source_hash
    assert res2.task_id == "task_2"
    assert len(res2.observations) == len(res1.observations)

    # Modify file - source_hash changes -> fresh analysis
    create_drawing_with_title_block(img_path)
    res3 = agent.process_image(img_path, task_id="task_3")
    assert res3.source_hash != res1.source_hash
    assert len(agent._cache) == 2

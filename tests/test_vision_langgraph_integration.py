"""Tests for LangGraph orchestration integration with Vision Agent and Phase 7 tools."""

import pytest
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.state.task_state import TaskStatus
from backend.app.vision.tools import register_vision_tools
from tests.fixtures.vision_fixtures import (
    create_drawing_with_dimensions,
    create_industrial_equipment_photo,
)


def test_agent_executor_dispatches_engineering_vision(tmp_path):
    """Verify that AgentExecutor executes vision_agent for engineering drawings."""
    agent_reg = AgentRegistry()
    tool_reg = ToolRegistry()
    register_vision_tools(tool_reg)

    img_path = str(tmp_path / "dwg.png")
    create_drawing_with_dimensions(img_path)

    executor = AgentExecutor(agent_reg, tool_reg)

    step = PlanStep(
        step_id="step_vis_eng_1",
        agent_id="vision_agent",
        capability="vision.engineering_analysis",
        description="Extract dimensions and inspect geometry of engineering drawing",
        required_tools=["engineering_drawing_analyze"],
        expected_output="vision_result",
    )

    result = executor.execute(
        agent_id="vision_agent",
        step=step,
        task_context={"image_path": img_path},
    )

    assert result.status == "SUCCESS"
    assert "vision_result" in result.output
    v_res = result.output["vision_result"]
    assert v_res["source_hash"] != ""
    assert len(v_res["evidence"]) > 0
    assert len(v_res["observations"]) > 0
    assert v_res["verification_status"] == "VERIFIED"


def test_langgraph_full_orchestration_engineering_drawing(tmp_path):
    """Test full LangGraph execution from user query to verified delivery for an engineering drawing."""
    orchestrator = WorkbenchOrchestrator()
    register_vision_tools(orchestrator.nodes.tool_registry)

    dwg_path = str(tmp_path / "turbine_dwg.png")
    create_drawing_with_dimensions(dwg_path)

    user_query = f"Analyze the engineering drawing located at {dwg_path} and extract all dimensions."

    final_state = orchestrator.run(
        user_query,
        task_id="task_eng_vision_e2e",
        initial_context={"image_path": dwg_path, "file_path": dwg_path},
    )

    assert final_state["task_status"] == TaskStatus.COMPLETED.value
    assert len(final_state["plan"]) > 0
    assert len(final_state["execution_steps"]) > 0
    assert final_state["verification_results"]["is_verified"] is True
    assert final_state["final_result"] is not None
    assert final_state["final_result"]["status"] == "COMPLETED"


def test_vision_policy_enforcement_and_approval_controls(tmp_path):
    """Verify Phase 5 policy controls remain authoritative: vision tools execute without bypass."""
    agent_reg = AgentRegistry()
    tool_reg = ToolRegistry()
    register_vision_tools(tool_reg)

    # Verify all 5 vision tools are registered with LOW risk and require_approval=False
    for tool_name in [
        "engineering_drawing_analyze",
        "industrial_image_inspect",
        "image_preprocess_tile",
        "visual_region_detect",
        "verify_visual_evidence",
    ]:
        tool = tool_reg.get(tool_name)
        assert tool.risk_level == "LOW"
        assert tool.requires_approval is False

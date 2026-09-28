"""Test D: Plan Construction and DAG/Registry Validation."""

import pytest
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.planner import PlanStep, PlanValidator
from backend.app.orchestration.errors import (
    InvalidPlanError,
    UnknownAgentError,
    UnknownToolError,
)


@pytest.fixture
def plan_validator():
    return PlanValidator(
        agent_registry=AgentRegistry(),
        tool_registry=ToolRegistry(),
    )


def test_valid_plan_passes_validation(plan_validator):
    """Verify structurally sound plan with registered agents and tools passes."""
    steps = [
        PlanStep(
            step_id="step_1",
            description="Ingest document",
            capability="document_extraction",
            agent_id="document_agent",
            required_tools=["file_read"],
            dependencies=[],
        ),
        PlanStep(
            step_id="step_2",
            description="Analyze evidence",
            capability="reasoning",
            agent_id="reasoning_agent",
            required_tools=[],
            dependencies=["step_1"],
        ),
    ]
    # Should not raise
    plan_validator.validate(steps)


def test_empty_plan_rejected(plan_validator):
    """Verify empty plan raises InvalidPlanError."""
    with pytest.raises(InvalidPlanError) as exc_info:
        plan_validator.validate([])
    assert "Plan cannot be empty" in str(exc_info.value)


def test_unknown_agent_rejected(plan_validator):
    """Verify plan referencing unregistered agent raises UnknownAgentError."""
    steps = [
        PlanStep(
            step_id="step_1",
            description="Run cloud agent",
            capability="reasoning",
            agent_id="external_cloud_gpt_agent",
        )
    ]
    with pytest.raises(UnknownAgentError):
        plan_validator.validate(steps)


def test_unknown_tool_rejected(plan_validator):
    """Verify plan referencing unregistered tool raises UnknownToolError."""
    steps = [
        PlanStep(
            step_id="step_1",
            description="Run web scraper",
            capability="reasoning",
            agent_id="reasoning_agent",
            required_tools=["unregistered_web_scraper"],
        )
    ]
    with pytest.raises(UnknownToolError):
        plan_validator.validate(steps)


def test_agent_missing_capability_rejected(plan_validator):
    """Verify step assigning capability that agent does not advertise is rejected."""
    steps = [
        PlanStep(
            step_id="step_1",
            description="Extract visual features",
            capability="visual_reasoning",
            agent_id="data_agent",  # data_agent does not do visual_reasoning
        )
    ]
    with pytest.raises(InvalidPlanError) as exc_info:
        plan_validator.validate(steps)
    assert "does not advertise required capability" in str(exc_info.value)


def test_invalid_dependency_rejected(plan_validator):
    """Verify dependency on non-existent step raises InvalidPlanError."""
    steps = [
        PlanStep(
            step_id="step_1",
            description="Analyze data",
            capability="calculation",
            agent_id="data_agent",
            dependencies=["non_existent_step"],
        )
    ]
    with pytest.raises(InvalidPlanError):
        plan_validator.validate(steps)


def test_circular_dependency_rejected(plan_validator):
    """Verify cycle in step dependencies raises InvalidPlanError."""
    steps = [
        PlanStep(
            step_id="s1",
            description="Step 1",
            capability="reasoning",
            agent_id="reasoning_agent",
            dependencies=["s2"],
        ),
        PlanStep(
            step_id="s2",
            description="Step 2",
            capability="reasoning",
            agent_id="reasoning_agent",
            dependencies=["s1"],
        ),
    ]
    with pytest.raises(InvalidPlanError) as exc_info:
        plan_validator.validate(steps)
    assert "Circular dependency detected" in str(exc_info.value)

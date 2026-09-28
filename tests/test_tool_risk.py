"""Test D: Tool Risk Metadata Integration from ToolRegistry."""

import pytest
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome


def test_tool_risk_metadata_incorporation():
    """Verify tool risk metadata from ToolRegistry influences policy decisions."""
    tool_registry = ToolRegistry()
    engine = PolicyEngine(tool_registry=tool_registry)

    # 1. file_read: LOW risk -> ALLOW
    s1 = PlanStep(
        step_id="s1",
        description="Read document",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )
    d1, r1 = engine.evaluate_plan([s1])
    assert d1.decision == PolicyOutcome.ALLOW
    assert r1.risk_level.value == "LOW"

    # 2. file_write: MEDIUM risk -> ALLOW (no approval required by default for local write)
    s2 = PlanStep(
        step_id="s2",
        description="Write output file",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_write"],
    )
    d2, r2 = engine.evaluate_plan([s2])
    assert d2.decision == PolicyOutcome.ALLOW
    assert r2.risk_level.value == "MEDIUM"

    # 3. python_calculation: MEDIUM risk -> ALLOW
    s3 = PlanStep(
        step_id="s3",
        description="Calculate metrics",
        capability="calculation",
        agent_id="data_agent",
        required_tools=["python_calculation"],
    )
    d3, r3 = engine.evaluate_plan([s3])
    assert d3.decision == PolicyOutcome.ALLOW
    assert r3.risk_level.value == "MEDIUM"

    # 4. sandbox_execute: HIGH risk, requires_approval=True -> REQUIRE_APPROVAL
    s4 = PlanStep(
        step_id="s4",
        description="Execute code in sandbox",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    d4, r4 = engine.evaluate_plan([s4])
    assert d4.decision == PolicyOutcome.REQUIRE_APPROVAL
    assert d4.requires_approval is True
    assert "sandbox_execute" in d4.flagged_tools

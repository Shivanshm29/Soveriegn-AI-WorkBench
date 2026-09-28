"""Test E: Fail-Closed Behavior for Unknown Tools."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome


def test_unknown_tool_fails_closed():
    """Verify plan with unknown tool is unconditionally denied (fail-closed)."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_bad_tool",
        description="Call invented tool",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=["nonexistent_arbitrary_tool"],
    )

    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert decision.status == "blocked"
    assert "FAIL_CLOSED_UNKNOWN_TOOL" in decision.matched_rules
    assert "nonexistent_arbitrary_tool" in decision.reason

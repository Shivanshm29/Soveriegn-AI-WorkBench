"""Test F: Fail-Closed Behavior for Unknown Agents."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome


def test_unknown_agent_fails_closed():
    """Verify plan with unknown agent is unconditionally denied (fail-closed)."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_bad_agent",
        description="Delegate to hallucinated agent",
        capability="reasoning",
        agent_id="nonexistent_rogue_agent",
        required_tools=["file_read"],
    )

    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert decision.status == "blocked"
    assert "FAIL_CLOSED_UNKNOWN_AGENT" in decision.matched_rules
    assert "nonexistent_rogue_agent" in decision.reason

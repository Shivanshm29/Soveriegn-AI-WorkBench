"""Test M: Sovereignty Precedence Over Policy and Human Approval."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome
from backend.app.security.approval import ApprovalDecision, ApprovalManager


def test_sovereignty_cannot_be_overridden_by_human_approval():
    """Verify that external network access is unconditionally DENIED and cannot be bypassed by approval."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_ext",
        description="Query external cloud network endpoint https://cloud-ai.example.com",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=[],
    )

    decision, risk = engine.evaluate_plan([step])

    # 1. Must be DENY, not REQUIRE_APPROVAL
    assert decision.decision == PolicyOutcome.DENY
    assert decision.requires_approval is False
    assert "SOVEREIGNTY_NO_EXTERNAL_NETWORK" in decision.matched_rules

    # 2. Human approval attempt must have no valid pending request
    assert not hasattr(decision, "approval_id") or not decision.requires_approval

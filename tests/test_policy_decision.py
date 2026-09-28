"""Test C: Policy Decisions (ALLOW, REQUIRE_APPROVAL, DENY)."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome, PolicyDecision
from backend.app.security.data_sensitivity import DataSensitivity


def test_policy_decision_allow():
    """Verify standard compliant plan evaluates to ALLOW."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_safe",
        description="Extract and summarize information",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=["file_read"],
    )
    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.ALLOW
    assert decision.status == "allowed"
    assert not decision.requires_approval
    assert "POLICY_ALLOW" in decision.matched_rules
    assert decision.policy_version == "1.0.0"


def test_policy_decision_require_approval():
    """Verify high-risk actions evaluate to REQUIRE_APPROVAL."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_sandbox",
        description="Execute generated script in sandbox",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.REQUIRE_APPROVAL
    assert decision.status == "requires_approval"
    assert decision.requires_approval is True
    assert "sandbox_execute" in decision.flagged_tools
    assert any("APPROVAL_REQUIRED" in rule for rule in decision.matched_rules)


def test_policy_decision_deny():
    """Verify denied actions (external network, cloud calls) evaluate to DENY."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_deny",
        description="Fetch remote update from external https://api.example.com",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=[],
    )
    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert decision.status == "blocked"
    assert not decision.requires_approval
    assert "SOVEREIGNTY_NO_EXTERNAL_NETWORK" in decision.matched_rules

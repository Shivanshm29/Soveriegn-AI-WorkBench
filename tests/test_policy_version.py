"""Test N: Policy Versioning in Decisions and Assessments."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine


def test_policy_decisions_preserve_policy_version():
    """Verify PolicyDecision and RiskAssessment records retain policy_version."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_v",
        description="Extract metrics",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=["file_read"],
    )

    decision, risk = engine.evaluate_plan([step])
    assert decision.policy_version == "1.0.0"
    assert risk.policy_version == "1.0.0"

    # Test custom policy version loading
    custom_engine = PolicyEngine()
    custom_engine.policy_version = "2.1.0"
    custom_engine.risk_engine.policy_version = "2.1.0"

    custom_dec, custom_risk = custom_engine.evaluate_plan([step])
    assert custom_dec.policy_version == "2.1.0"
    assert custom_risk.policy_version == "2.1.0"

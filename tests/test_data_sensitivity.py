"""Test B: Data Sensitivity Levels and Policy Engine Integration."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.data_sensitivity import DataSensitivity, parse_data_sensitivity
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome


def test_data_sensitivity_parsing_and_defaults():
    """Verify parsing and fail-closed default behavior."""
    assert parse_data_sensitivity("PUBLIC") == DataSensitivity.PUBLIC
    assert parse_data_sensitivity("internal") == DataSensitivity.INTERNAL
    assert parse_data_sensitivity("CONFIDENTIAL") == DataSensitivity.CONFIDENTIAL
    assert parse_data_sensitivity("restricted") == DataSensitivity.RESTRICTED
    assert parse_data_sensitivity(None) == DataSensitivity.INTERNAL
    # Unknown string fails closed to RESTRICTED
    assert parse_data_sensitivity("TOP_SECRET_UNKNOWN") == DataSensitivity.RESTRICTED


def test_data_sensitivity_reaches_policy_engine():
    """Verify RESTRICTED data triggers REQUIRE_APPROVAL even for simple read steps."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="step_read",
        description="Read document content",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )

    # PUBLIC data -> ALLOW
    pub_decision, pub_risk = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.PUBLIC)
    assert pub_decision.decision == PolicyOutcome.ALLOW
    assert not pub_decision.requires_approval

    # INTERNAL data -> ALLOW
    int_decision, int_risk = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.INTERNAL)
    assert int_decision.decision == PolicyOutcome.ALLOW
    assert not int_decision.requires_approval

    # CONFIDENTIAL data -> ALLOW with sensitive data access factor
    conf_decision, conf_risk = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.CONFIDENTIAL)
    assert conf_decision.decision == PolicyOutcome.ALLOW
    assert "sensitive_data_access" in conf_risk.risk_factors

    # RESTRICTED data -> REQUIRE_APPROVAL (policy requires approval for restricted data)
    rest_decision, rest_risk = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.RESTRICTED)
    assert rest_decision.decision == PolicyOutcome.REQUIRE_APPROVAL
    assert rest_decision.requires_approval is True
    assert "APPROVAL_REQUIRED_DATA_SENSITIVITY" in rest_decision.matched_rules

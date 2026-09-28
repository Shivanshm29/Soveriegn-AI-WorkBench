"""Test P: Comprehensive Fail-Closed Behavior."""

import pytest
from datetime import datetime, timezone, timedelta
from backend.app.orchestration.planner import PlanStep
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome
from backend.app.security.approval import ApprovalManager, ApprovalRequest, ApprovalDecision, ApprovalStatus


def test_missing_policy_config_fails_closed(tmp_path):
    """Verify engine fails closed if policy config is missing or unreadable."""
    nonexistent_path = str(tmp_path / "nonexistent_policy.yaml")
    engine = PolicyEngine(policy_config_path=nonexistent_path)

    step = PlanStep(
        step_id="step_test",
        description="Harmless read step",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )

    decision, risk = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert "FAIL_CLOSED_NO_CONFIG" in decision.matched_rules


def test_invalid_approval_id_fails_closed():
    """Verify mismatched approval ID fails closed."""
    step = PlanStep(
        step_id="s1",
        description="Run code",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    engine = PolicyEngine()
    _, risk = engine.evaluate_plan([step])
    req = ApprovalManager.create_request("t1", "p1", risk, [step])

    bad_decision = ApprovalDecision(
        approval_id="wrong-mismatched-id",
        decision="APPROVED",
        approver="admin",
    )
    is_valid, reason, status = ApprovalManager.validate_approval(req, bad_decision, [step])
    assert not is_valid
    assert "mismatch" in reason.lower()
    assert status == ApprovalStatus.REJECTED


def test_blank_approver_fails_closed():
    """Verify approval without identifiable approver fails closed."""
    step = PlanStep(
        step_id="s1",
        description="Run code",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    engine = PolicyEngine()
    _, risk = engine.evaluate_plan([step])
    req = ApprovalManager.create_request("t1", "p1", risk, [step])

    blank_decision = ApprovalDecision(
        approval_id=req.approval_id,
        decision="APPROVED",
        approver="   ",  # Blank
    )
    is_valid, reason, status = ApprovalManager.validate_approval(req, blank_decision, [step])
    assert not is_valid
    assert "approver identity" in reason.lower()
    assert status == ApprovalStatus.REJECTED

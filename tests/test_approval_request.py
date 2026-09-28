"""Test G: Approval Request Construction and Schema Validation."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.security.risk import RiskEngine, RiskLevel
from backend.app.security.approval import ApprovalManager, ApprovalStatus, ApprovalRequest


def test_approval_request_creation():
    """Verify ApprovalRequest object contains all required fields and valid hashes."""
    engine = RiskEngine()
    step = PlanStep(
        step_id="step_code",
        description="Run sandbox calculation",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )

    assessment = engine.assess_plan("task-100", "plan-100", [step])
    request = ApprovalManager.create_request(
        task_id="task-100",
        plan_id="plan-100",
        risk_assessment=assessment,
        plan_steps=[step],
        policy_version="1.0.0",
    )

    assert request.approval_id is not None
    assert request.task_id == "task-100"
    assert request.plan_id == "plan-100"
    assert request.status == ApprovalStatus.PENDING
    assert request.risk_level == RiskLevel.HIGH.value
    assert "sandbox_execute" in request.affected_tools
    assert request.plan_hash != ""
    assert request.created_at is not None
    assert request.expires_at > request.created_at
    assert not request.is_expired()

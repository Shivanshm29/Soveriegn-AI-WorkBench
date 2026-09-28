"""Phase 5 Acceptance Test Suite — Risk, Policy & Human Approval."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from backend.app.config.settings import get_settings
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelResponse
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.state.events import EventType
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor, AgentExecutionResult
from backend.app.security.risk import RiskEngine, RiskLevel, RiskFactor
from backend.app.security.data_sensitivity import DataSensitivity, parse_data_sensitivity
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome, PolicyDecision
from backend.app.security.approval import (
    ApprovalRequest,
    ApprovalDecision,
    ApprovalManager,
    ApprovalStatus,
    compute_plan_hash,
)


def test_acceptance_01_previous_phases_pass():
    """Acceptance 1: Verify Phase 0-4 foundations are functioning."""
    settings = get_settings()
    assert settings.APP_ENV is not None
    assert settings.SOVEREIGN_MODE is True
    assert len(ToolRegistry().list()) == 8
    assert len(AgentRegistry().list()) == 7


def test_acceptance_02_risk_assessment_works():
    """Acceptance 2: Risk assessment calculates deterministic scores and risk levels."""
    engine = RiskEngine()
    step_low = PlanStep(
        step_id="s1",
        description="Read file",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )
    ass_low = engine.assess_plan("t1", "p1", [step_low], DataSensitivity.PUBLIC)
    assert ass_low.risk_level == RiskLevel.LOW

    step_high = PlanStep(
        step_id="s2",
        description="Run code in sandbox",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    ass_high = engine.assess_plan("t2", "p2", [step_high], DataSensitivity.INTERNAL)
    assert ass_high.risk_level == RiskLevel.HIGH
    assert RiskFactor.CODE_EXECUTION.value in ass_high.risk_factors


def test_acceptance_03_data_sensitivity_works():
    """Acceptance 3: Data sensitivity classification influences policy decision."""
    engine = PolicyEngine()
    step = PlanStep(
        step_id="s1",
        description="Analyze sensitive telemetry",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=["file_read"],
    )
    # PUBLIC -> ALLOW
    d_pub, _ = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.PUBLIC)
    assert d_pub.decision == PolicyOutcome.ALLOW

    # RESTRICTED -> REQUIRE_APPROVAL
    d_rest, _ = engine.evaluate_plan([step], data_sensitivity=DataSensitivity.RESTRICTED)
    assert d_rest.decision == PolicyOutcome.REQUIRE_APPROVAL
    assert d_rest.requires_approval is True


def test_acceptance_04_policy_decision_works():
    """Acceptance 4: Policy engine outputs ALLOW, REQUIRE_APPROVAL, or DENY."""
    engine = PolicyEngine()
    step_safe = PlanStep(step_id="s1", description="Read", capability="reasoning", agent_id="reasoning_agent", required_tools=["file_read"])
    d_allow, _ = engine.evaluate_plan([step_safe])
    assert d_allow.decision == PolicyOutcome.ALLOW

    step_app = PlanStep(step_id="s2", description="Run", capability="code_execution", agent_id="coding_agent", required_tools=["sandbox_execute"])
    d_app, _ = engine.evaluate_plan([step_app])
    assert d_app.decision == PolicyOutcome.REQUIRE_APPROVAL

    step_deny = PlanStep(step_id="s3", description="Send external network ping", capability="reasoning", agent_id="reasoning_agent")
    d_deny, _ = engine.evaluate_plan([step_deny])
    assert d_deny.decision == PolicyOutcome.DENY


def test_acceptance_05_tool_risk_metadata_works():
    """Acceptance 5: Tool registry risk metadata drives policy assessment."""
    engine = PolicyEngine()
    step = PlanStep(step_id="s", description="Execute code", capability="code_execution", agent_id="coding_agent", required_tools=["sandbox_execute"])
    decision, risk = engine.evaluate_plan([step])
    assert "sandbox_execute" in risk.affected_tools
    assert "sandbox_execute" in decision.flagged_tools


def test_acceptance_06_unknown_tools_fail_closed():
    """Acceptance 6: Unknown tool in plan causes unconditional DENY."""
    engine = PolicyEngine()
    step = PlanStep(step_id="s", description="Bad", capability="reasoning", agent_id="reasoning_agent", required_tools=["nonexistent_tool_x"])
    decision, _ = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert "FAIL_CLOSED_UNKNOWN_TOOL" in decision.matched_rules


def test_acceptance_07_unknown_agents_fail_closed():
    """Acceptance 7: Unknown agent in plan causes unconditional DENY."""
    engine = PolicyEngine()
    step = PlanStep(step_id="s", description="Bad", capability="reasoning", agent_id="nonexistent_agent_y", required_tools=["file_read"])
    decision, _ = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert "FAIL_CLOSED_UNKNOWN_AGENT" in decision.matched_rules


def test_acceptance_08_approval_requests_work():
    """Acceptance 8: Approval requests are constructed with plan hash and expiration."""
    engine = RiskEngine()
    step = PlanStep(step_id="s", description="Sandbox", capability="code_execution", agent_id="coding_agent", required_tools=["sandbox_execute"])
    risk = engine.assess_plan("t1", "p1", [step])
    req = ApprovalManager.create_request("t1", "p1", risk, [step])

    assert req.approval_id is not None
    assert req.status == ApprovalStatus.PENDING
    assert req.plan_hash != ""
    assert not req.is_expired()


def test_acceptance_09_waiting_approval_state_and_pause(tmp_path):
    """Acceptance 9: Approval requirement halts execution at WAITING_APPROVAL without executing tools."""
    store = LocalStateStore(base_dir=tmp_path)
    exec_mock = MagicMock(spec=AgentExecutor)
    orchestrator = WorkbenchOrchestrator(agent_executor=exec_mock, state_store=store)

    res = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-pause",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert res["task_status"] == TaskStatus.WAITING_APPROVAL.value
    assert res.get("approval_request") is not None
    exec_mock.execute.assert_not_called()


def test_acceptance_10_approval_grant_and_resume(tmp_path):
    """Acceptance 10: Approved decision resumes execution to COMPLETED."""
    store = LocalStateStore(base_dir=tmp_path)
    exec_mock = MagicMock(spec=AgentExecutor)
    exec_mock.execute.return_value = AgentExecutionResult(status="SUCCESS", output={"res": 1})
    orchestrator = WorkbenchOrchestrator(agent_executor=exec_mock, state_store=store)

    res1 = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-resume",
        metadata={"required_capabilities": ["code_execution"]},
    )
    app_id = res1["approval_request"]["approval_id"]

    decision = ApprovalDecision(
        approval_id=app_id,
        decision="APPROVED",
        approver="senior_lead",
        reason="Verified and authorized",
    )
    res2 = orchestrator.submit_approval("task-acc-resume", decision)
    assert res2["task_status"] == TaskStatus.COMPLETED.value
    assert exec_mock.execute.called


def test_acceptance_11_approval_rejection_works(tmp_path):
    """Acceptance 11: Rejection decision fails task without running tools."""
    store = LocalStateStore(base_dir=tmp_path)
    exec_mock = MagicMock(spec=AgentExecutor)
    orchestrator = WorkbenchOrchestrator(agent_executor=exec_mock, state_store=store)

    res1 = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-reject",
        metadata={"required_capabilities": ["code_execution"]},
    )
    app_id = res1["approval_request"]["approval_id"]

    decision = ApprovalDecision(
        approval_id=app_id,
        decision="REJECTED",
        approver="security_audit",
        reason="Rejected due to policy violation",
    )
    res2 = orchestrator.submit_approval("task-acc-reject", decision)
    assert res2["task_status"] == TaskStatus.FAILED.value
    exec_mock.execute.assert_not_called()


def test_acceptance_12_approval_expiration_works(tmp_path):
    """Acceptance 12: Expired approvals fail closed."""
    store = LocalStateStore(base_dir=tmp_path)
    orchestrator = WorkbenchOrchestrator(state_store=store)

    res = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-expire",
        metadata={"required_capabilities": ["code_execution"]},
    )
    task_rec = store.get_task("task-acc-expire")
    req = ApprovalRequest.model_validate(task_rec.context["approval_request"])
    req.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    task_rec.context["approval_request"] = req.to_dict()
    store.save_task(task_rec)

    decision = ApprovalDecision(approval_id=req.approval_id, decision="APPROVED", approver="lead")
    res_final = orchestrator.submit_approval("task-acc-expire", decision)
    assert res_final["task_status"] == TaskStatus.FAILED.value
    assert any("expired" in err.lower() for err in res_final["errors"])


def test_acceptance_13_approval_scope_tampering_check(tmp_path):
    """Acceptance 13: Plan modifications invalidate prior approval."""
    store = LocalStateStore(base_dir=tmp_path)
    orchestrator = WorkbenchOrchestrator(state_store=store)

    res = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-tamper",
        metadata={"required_capabilities": ["code_execution"]},
    )
    task_rec = store.get_task("task-acc-tamper")
    tampered_plan = list(task_rec.context["plan"])
    tampered_plan.append({
        "step_id": "rogue",
        "description": "unauthorized",
        "capability": "code_execution",
        "agent_id": "coding_agent",
        "required_tools": ["sandbox_execute"],
        "dependencies": [],
    })
    task_rec.context["plan"] = tampered_plan
    store.save_task(task_rec)

    decision = ApprovalDecision(approval_id=res["approval_request"]["approval_id"], decision="APPROVED", approver="lead")
    res_final = orchestrator.submit_approval("task-acc-tamper", decision)
    assert res_final["task_status"] == TaskStatus.FAILED.value
    assert any("modified" in err.lower() for err in res_final["errors"])


def test_acceptance_14_policy_versioning_works():
    """Acceptance 14: Decisions and assessments preserve policy version."""
    engine = PolicyEngine()
    step = PlanStep(step_id="s", description="Test", capability="reasoning", agent_id="reasoning_agent", required_tools=["file_read"])
    decision, risk = engine.evaluate_plan([step])
    assert decision.policy_version == "1.0.0"
    assert risk.policy_version == "1.0.0"


def test_acceptance_15_audit_events_emitted(tmp_path):
    """Acceptance 15: Policy and approval audit events recorded."""
    store = LocalStateStore(base_dir=tmp_path)
    exec_mock = MagicMock(spec=AgentExecutor)
    exec_mock.execute.return_value = AgentExecutionResult(status="SUCCESS", output={})
    orchestrator = WorkbenchOrchestrator(agent_executor=exec_mock, state_store=store)

    res = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-events",
        metadata={"required_capabilities": ["code_execution"]},
    )
    events = [e.event_type.value for e in store.get_events("task-acc-events")]
    assert "RISK_ASSESSMENT_CREATED" in events
    assert "POLICY_EVALUATED" in events
    assert "APPROVAL_REQUESTED" in events


def test_acceptance_16_sovereignty_cannot_be_bypassed():
    """Acceptance 16: External network calls are DENIED regardless of approval."""
    engine = PolicyEngine()
    step = PlanStep(step_id="s", description="Access https://external.cloud", capability="reasoning", agent_id="reasoning_agent")
    decision, _ = engine.evaluate_plan([step])
    assert decision.decision == PolicyOutcome.DENY
    assert decision.requires_approval is False


def test_acceptance_17_no_infinite_approval_loops(tmp_path):
    """Acceptance 17: Approval validation terminates deterministically without loops."""
    store = LocalStateStore(base_dir=tmp_path)
    orchestrator = WorkbenchOrchestrator(state_store=store)

    res = orchestrator.run(
        user_request="Execute python script in sandbox",
        task_id="task-acc-noloop",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert res["task_status"] == TaskStatus.WAITING_APPROVAL.value
    # Resubmitting with reject immediately terminates
    decision = ApprovalDecision(approval_id=res["approval_request"]["approval_id"], decision="REJECTED", approver="audit")
    res_final = orchestrator.submit_approval("task-acc-noloop", decision)
    assert res_final["task_status"] == TaskStatus.FAILED.value


def test_acceptance_18_no_phase_6_functionality():
    """Acceptance 18: Verify no Phase 7+ features (RAG, sandbox execution) implemented."""
    with pytest.raises(ImportError):
        import backend.app.rag  # type: ignore
    with pytest.raises(ImportError):
        import backend.app.sandbox  # type: ignore


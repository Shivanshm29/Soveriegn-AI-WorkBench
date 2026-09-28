"""Test O: Audit Events for Policy and Approval Lifecycles."""

import pytest
from unittest.mock import MagicMock
from backend.app.state.store import LocalStateStore
from backend.app.state.events import EventType
from backend.app.security.approval import ApprovalDecision
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor, AgentExecutionResult


def test_audit_events_recorded_during_policy_and_approval_workflow(tmp_path):
    """Verify RISK_ASSESSMENT_CREATED, POLICY_EVALUATED, APPROVAL_REQUESTED, and APPROVAL_APPROVED events."""
    store = LocalStateStore(base_dir=tmp_path)
    agent_exec_mock = MagicMock(spec=AgentExecutor)
    agent_exec_mock.execute.return_value = AgentExecutionResult(status="SUCCESS", output={"result": 100})

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # 1. Run task requiring approval
    res = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-events-test",
        metadata={"required_capabilities": ["code_execution"]},
    )
    events_1 = store.get_events("task-events-test")
    event_types_1 = [e.event_type for e in events_1]

    # Verify initial policy events
    assert EventType.RISK_ASSESSMENT_CREATED in event_types_1
    assert EventType.POLICY_EVALUATED in event_types_1
    assert EventType.APPROVAL_REQUESTED in event_types_1

    # 2. Grant approval
    decision = ApprovalDecision(
        approval_id=res["approval_request"]["approval_id"],
        decision="APPROVED",
        approver="auditor_lead",
        reason="Approved per protocol",
    )
    res_final = orchestrator.submit_approval("task-events-test", decision)

    events_2 = store.get_events("task-events-test")
    event_types_2 = [e.event_type for e in events_2]

    # Verify resume and completion events
    assert EventType.APPROVAL_APPROVED in event_types_2
    assert EventType.TASK_STATUS_CHANGED in event_types_2

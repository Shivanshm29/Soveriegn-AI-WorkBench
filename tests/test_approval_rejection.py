"""Test J: Approval Rejection Behavior."""

import pytest
from unittest.mock import MagicMock
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.security.approval import ApprovalDecision
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor


def test_approval_rejection_halts_execution_and_fails(tmp_path):
    """Verify that submitting a REJECTED decision fails task without executing protected tools."""
    store = LocalStateStore(base_dir=tmp_path)
    agent_exec_mock = MagicMock(spec=AgentExecutor)

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # 1. Run task requiring approval
    res = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-reject-test",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert res["task_status"] == TaskStatus.WAITING_APPROVAL.value
    approval_req = res["approval_request"]

    # 2. Reject approval
    decision = ApprovalDecision(
        approval_id=approval_req["approval_id"],
        decision="REJECTED",
        approver="security_officer",
        reason="Operation deemed unsafe by security audit",
    )

    # 3. Submit rejection
    resumed = orchestrator.submit_approval("task-reject-test", decision)

    # 4. Must be marked FAILED, tool NOT executed
    assert resumed["task_status"] == TaskStatus.FAILED.value
    agent_exec_mock.execute.assert_not_called()
    assert any("Approval rejected" in err for err in resumed["errors"])

"""Test I: Approval Grant and Resume Execution."""

import pytest
from unittest.mock import MagicMock
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.security.approval import ApprovalDecision
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor, AgentExecutionResult


def test_approval_grant_resumes_execution_to_completion(tmp_path):
    """Verify that submitting an APPROVED decision resumes execution and completes successfully."""
    store = LocalStateStore(base_dir=tmp_path)

    # Mock agent executor so the code execution succeeds
    agent_exec_mock = MagicMock(spec=AgentExecutor)
    agent_exec_mock.execute.return_value = AgentExecutionResult(
        status="SUCCESS",
        output={"calculation_result": 42},
    )

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # 1. Initiate task that requires approval
    initial_result = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-grant-test",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert initial_result["task_status"] == TaskStatus.WAITING_APPROVAL.value
    approval_req = initial_result["approval_request"]
    approval_id = approval_req["approval_id"]

    # 2. Grant approval
    decision = ApprovalDecision(
        approval_id=approval_id,
        decision="APPROVED",
        approver="admin_supervisor",
        reason="Execution authorized for benchmark analysis",
        authorization_scope=approval_req["authorization_scope"],
    )

    # 3. Resume task via submit_approval
    resumed_result = orchestrator.submit_approval("task-grant-test", decision)

    # 4. Task must complete successfully
    assert resumed_result["task_status"] == TaskStatus.COMPLETED.value
    assert agent_exec_mock.execute.called
    assert resumed_result["final_result"]["status"] == "COMPLETED"
    assert resumed_result["final_result"]["outputs"]["calculation_result"] == 42

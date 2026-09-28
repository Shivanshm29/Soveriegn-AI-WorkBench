"""Test K: Approval Expiration Behavior."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.security.approval import ApprovalDecision, ApprovalRequest, ApprovalManager
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor


def test_expired_approval_cannot_authorize_execution(tmp_path):
    """Verify that an expired approval request fails closed and prevents execution."""
    store = LocalStateStore(base_dir=tmp_path)
    agent_exec_mock = MagicMock(spec=AgentExecutor)

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # 1. Run task requiring approval
    res = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-expire-test",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert res["task_status"] == TaskStatus.WAITING_APPROVAL.value

    # 2. Artificially expire the request in state store
    task_rec = store.get_task("task-expire-test")
    app_req_dict = task_rec.context["approval_request"]
    app_req = ApprovalRequest.model_validate(app_req_dict)
    # Set expires_at in the past
    app_req.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    task_rec.context["approval_request"] = app_req.to_dict()
    store.save_task(task_rec)

    # 3. Attempt to submit approval on expired request
    decision = ApprovalDecision(
        approval_id=app_req.approval_id,
        decision="APPROVED",
        approver="admin_supervisor",
        reason="Approved after deadline",
    )

    resumed = orchestrator.submit_approval("task-expire-test", decision)

    # 4. Must fail closed, not executed
    assert resumed["task_status"] == TaskStatus.FAILED.value
    agent_exec_mock.execute.assert_not_called()
    assert any("expired" in err.lower() for err in resumed["errors"])

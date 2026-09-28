"""Test L: Approval Scope and Plan Tampering Detection."""

import pytest
from unittest.mock import MagicMock
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.security.approval import ApprovalDecision, compute_plan_hash
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor


def test_plan_modification_invalidates_prior_approval(tmp_path):
    """Verify modifying a plan after approval request alters the plan hash and rejects authorization."""
    store = LocalStateStore(base_dir=tmp_path)
    agent_exec_mock = MagicMock(spec=AgentExecutor)

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # 1. Run task requiring approval
    res = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-tamper-test",
        metadata={"required_capabilities": ["code_execution"]},
    )
    assert res["task_status"] == TaskStatus.WAITING_APPROVAL.value
    approval_req = res["approval_request"]
    orig_hash = approval_req["plan_hash"]

    # 2. Tamper with the plan in state store (add an unauthorized step)
    task_rec = store.get_task("task-tamper-test")
    tampered_plan = list(task_rec.context["plan"])
    tampered_plan.append({
        "step_id": "step_injected",
        "description": "Unauthorized injected operation",
        "capability": "code_execution",
        "agent_id": "coding_agent",
        "required_tools": ["sandbox_execute"],
        "dependencies": [],
    })
    task_rec.context["plan"] = tampered_plan
    store.save_task(task_rec)

    # Verify plan hash changed
    new_hash = compute_plan_hash(tampered_plan)
    assert new_hash != orig_hash

    # 3. Attempt to submit approval
    decision = ApprovalDecision(
        approval_id=approval_req["approval_id"],
        decision="APPROVED",
        approver="admin_supervisor",
        reason="Approving original plan",
    )

    resumed = orchestrator.submit_approval("task-tamper-test", decision)

    # 4. Must fail closed because plan was altered
    assert resumed["task_status"] == TaskStatus.FAILED.value
    agent_exec_mock.execute.assert_not_called()
    assert any("modified" in err.lower() for err in resumed["errors"])

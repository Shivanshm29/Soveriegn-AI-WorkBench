"""Test H: Approval Pause Behavior in Orchestration Graph."""

import pytest
from unittest.mock import MagicMock
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelResponse
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor


def test_approval_requirement_pauses_execution(tmp_path):
    """Verify that when approval is required, execution stops at WAITING_APPROVAL without calling tools."""
    store = LocalStateStore(base_dir=tmp_path)
    agent_exec_mock = MagicMock(spec=AgentExecutor)

    orchestrator = WorkbenchOrchestrator(
        agent_executor=agent_exec_mock,
        state_store=store,
    )

    # Run task requiring sandbox_execute (which requires approval)
    result = orchestrator.run(
        user_request="Execute python script to analyze dataset",
        task_id="task-pause-test",
        metadata={"required_capabilities": ["code_execution"]},
    )

    # 1. State must be WAITING_APPROVAL
    assert result["task_status"] == TaskStatus.WAITING_APPROVAL.value

    # 2. ApprovalRequest must be generated
    assert result.get("approval_request") is not None
    assert result["approval_request"]["status"] == "PENDING"
    assert "sandbox_execute" in result["approval_request"]["affected_tools"]

    # 3. Agent executor must NOT have executed any step
    agent_exec_mock.execute.assert_not_called()

    # 4. State store must reflect WAITING_APPROVAL
    saved_task = store.get_task("task-pause-test")
    assert saved_task is not None
    assert saved_task.status == TaskStatus.WAITING_APPROVAL

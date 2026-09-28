"""End-to-End Test: Full Approval Lifecycle from Task to Delivery."""

import pytest
from unittest.mock import MagicMock
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelResponse
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.security.approval import ApprovalDecision
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor, AgentExecutionResult


def test_end_to_end_approval_workflow(tmp_path):
    """
    Demonstrate complete end-to-end flow:
    Task -> Understand -> Route -> Plan -> Risk Assessment -> Policy ->
    REQUIRE_APPROVAL -> WAITING_APPROVAL -> Submit Approval ->
    EXECUTE -> OBSERVE -> VERIFY -> DELIVER
    """
    store = LocalStateStore(base_dir=tmp_path)

    # Mock local runtime for deterministic understanding
    mock_runtime = MagicMock(spec=ModelRuntime)
    mock_runtime.chat.return_value = ModelResponse(
        content='{"intent": "Execute code analysis", "capabilities": ["code_execution"], "modalities": ["text"], "complexity": "MEDIUM", "output_type": "analysis"}',
        model="Qwen/Qwen3-4B",
    )

    # Mock agent executor for execution phase
    mock_executor = MagicMock(spec=AgentExecutor)
    mock_executor.execute.return_value = AgentExecutionResult(
        status="SUCCESS",
        output={"analysis_output": "Execution completed successfully with verified checksums."},
    )

    orchestrator = WorkbenchOrchestrator(
        model_runtime=mock_runtime,
        agent_executor=mock_executor,
        state_store=store,
    )

    # Step 1: User submits a request that requires high-risk tool execution
    task_id = "task-e2e-approval-001"
    initial_state = orchestrator.run(
        user_request="Please run an analytical Python script in the sandbox to verify component tolerances.",
        task_id=task_id,
        data_sensitivity="INTERNAL",
    )

    # Verify task successfully stopped at WAITING_APPROVAL
    assert initial_state["task_status"] == TaskStatus.WAITING_APPROVAL.value
    assert initial_state.get("risk_assessment") is not None
    assert initial_state["risk_assessment"]["risk_level"] in ("HIGH", "CRITICAL")
    assert initial_state.get("policy_decision") is not None
    assert initial_state["policy_decision"]["decision"] == "REQUIRE_APPROVAL"
    assert initial_state.get("approval_request") is not None

    approval_req = initial_state["approval_request"]
    approval_id = approval_req["approval_id"]

    # Verify no execution has taken place yet
    mock_executor.execute.assert_not_called()

    # Step 2: Human supervisor reviews the request and provides formal authorization
    decision = ApprovalDecision(
        approval_id=approval_id,
        decision="APPROVED",
        approver="lead_engineer_alice",
        reason="Tolerance script verified and authorized for component run.",
        authorization_scope=approval_req["authorization_scope"],
    )

    # Step 3: Submit authorization decision and resume execution
    final_state = orchestrator.submit_approval(task_id, decision)

    # Step 4: Verify the graph executed through to DELIVER and COMPLETED
    assert final_state["task_status"] == TaskStatus.COMPLETED.value
    assert final_state["final_result"]["status"] == "COMPLETED"
    assert "analysis_output" in final_state["final_result"]["outputs"]
    assert mock_executor.execute.called

    # Step 5: Verify persisted history in state store
    persisted_task = store.get_task(task_id)
    assert persisted_task.status == TaskStatus.COMPLETED
    events = store.get_events(task_id)
    event_names = [e.event_type.value for e in events]

    assert "RISK_ASSESSMENT_CREATED" in event_names
    assert "POLICY_EVALUATED" in event_names
    assert "APPROVAL_REQUESTED" in event_names
    assert "APPROVAL_APPROVED" in event_names
    assert "STEP_STARTED" in event_names
    assert "STEP_COMPLETED" in event_names
    assert "TASK_STATUS_CHANGED" in event_names

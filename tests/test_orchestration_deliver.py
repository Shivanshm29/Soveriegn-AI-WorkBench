"""Test K: Deliver Node and Terminal Result Aggregation."""

import pytest
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.state.task_state import TaskStatus


def test_deliver_node_aggregates_successful_outputs():
    """Verify deliver node aggregates step outputs into final_result on success."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler(
        "reasoning_agent",
        lambda step, ctx: {"summary": "Completed analysis successfully"},
    )

    final_state = orchestrator.run("Summarize text")
    assert final_state["task_status"] == TaskStatus.COMPLETED.value
    assert final_state["final_result"] is not None
    assert final_state["final_result"]["status"] == "COMPLETED"
    assert final_state["final_result"]["outputs"]["summary"] == "Completed analysis successfully"


def test_deliver_node_records_errors_on_failure():
    """Verify deliver node aggregates errors when task fails."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler(
        "reasoning_agent",
        lambda step, ctx: (_ for _ in ()).throw(RuntimeError("Unrecoverable error")),
    )

    final_state = orchestrator.run("Failing task")
    assert final_state["task_status"] == TaskStatus.FAILED.value
    assert final_state["final_result"]["status"] == "FAILED"
    assert len(final_state["final_result"]["errors"]) > 0

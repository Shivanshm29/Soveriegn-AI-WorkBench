"""Test L: Task Isolation and Context Segregation."""

import pytest
from backend.app.orchestration.graph import WorkbenchOrchestrator


def test_concurrent_tasks_maintain_complete_isolation():
    """Verify separate task invocations on the same orchestrator do not share or leak state."""
    orchestrator = WorkbenchOrchestrator()

    # Register handlers returning task-specific content
    def dynamic_handler(step, ctx):
        req = ctx.get("user_request", "")
        return {"processed_request": req}

    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", dynamic_handler)

    state1 = orchestrator.run("Alpha inspection request", task_id="task-alpha")
    state2 = orchestrator.run("Beta financial audit request", task_id="task-beta")

    # Verify task IDs
    assert state1["task_id"] == "task-alpha"
    assert state2["task_id"] == "task-beta"

    # Verify requests
    assert state1["user_request"] == "Alpha inspection request"
    assert state2["user_request"] == "Beta financial audit request"

    # Verify outputs are isolated
    assert state1["final_result"]["outputs"]["processed_request"] == "Alpha inspection request"
    assert state2["final_result"]["outputs"]["processed_request"] == "Beta financial audit request"

    # Verify execution steps do not cross over
    for step in state1["execution_steps"]:
        assert step["task_id"] == "task-alpha"

    for step in state2["execution_steps"]:
        assert step["task_id"] == "task-beta"

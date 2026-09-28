"""Test H: Replanning Loop and Failure Recovery."""

import pytest
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.orchestration.execution import AgentExecutor


def test_replan_loop_recovers_after_transient_failure():
    """Verify workflow executes OBSERVE -> REPLAN -> EXECUTE on recoverable failure, then succeeds."""
    orchestrator = WorkbenchOrchestrator()
    attempt = 0

    def flaky_handler(step, ctx):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise RuntimeError("Transient socket read timeout")
        return {"result": "Recovered on attempt 2"}

    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", flaky_handler)

    final_state = orchestrator.run("Perform resilient reasoning task")

    assert final_state["task_status"] == "COMPLETED"
    assert final_state["retry_count"] == 1
    assert attempt == 2
    assert final_state["final_result"]["status"] == "COMPLETED"
    assert final_state["final_result"]["outputs"]["result"] == "Recovered on attempt 2"

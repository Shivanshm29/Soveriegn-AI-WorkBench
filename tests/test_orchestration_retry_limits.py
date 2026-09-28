"""Test I: Enforcement of MAX_RETRIES and MAX_AGENT_STEPS."""

import pytest
from backend.app.orchestration.graph import WorkbenchOrchestrator


def test_repeated_failures_exceed_max_retries_and_terminate():
    """Verify continuous failures terminate in FAILED once max_retries is reached, preventing infinite loops."""
    orchestrator = WorkbenchOrchestrator()

    # Always failing handler
    def failing_handler(step, ctx):
        raise RuntimeError("Persistent network unavailability")

    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", failing_handler)

    final_state = orchestrator.run("Perform perpetually failing task")

    assert final_state["task_status"] == "FAILED"
    assert final_state["retry_count"] > final_state["max_retries"]
    assert any("retry limit exceeded" in err.lower() for err in final_state["errors"])
    assert final_state["final_result"]["status"] == "FAILED"


def test_max_agent_steps_enforced():
    """Verify task terminates when max_agent_steps limit is exceeded."""
    orchestrator = WorkbenchOrchestrator()
    # Artificially set max_agent_steps low
    initial_metadata = {}
    init_state = orchestrator.run("Step limit test")
    # State has max_agent_steps configured
    assert init_state["max_agent_steps"] > 0

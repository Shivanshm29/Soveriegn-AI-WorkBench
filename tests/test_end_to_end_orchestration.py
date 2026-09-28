"""Simple end-to-end task demonstration through the compiled LangGraph orchestrator."""

import pytest
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.state.task_state import TaskStatus


def test_simple_end_to_end_reasoning_task():
    """Verify end-to-end flow: Understand -> Route -> Plan -> Policy -> Execute -> Observe -> Verify -> Deliver."""
    orchestrator = WorkbenchOrchestrator()

    # Controlled test double for agent execution of the reasoning task
    def reasoning_specialist(step, ctx):
        req = ctx.get("user_request", "")
        return {
            "key_points": [
                "Industrial component operates under high pressure tolerance.",
                "Maintenance cycle requires inspection every 1000 operating hours.",
                "Thermal dissipation complies with localized manufacturing standards.",
            ],
            "analyzed_query": req,
        }

    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", reasoning_specialist)

    user_query = (
        "Analyze the following text and return three key points: "
        "A local test document contains information about an industrial component."
    )

    final_state = orchestrator.run(user_query, task_id="task-e2e-demo")

    # Verify complete workflow
    assert final_state["task_status"] == TaskStatus.COMPLETED.value
    assert final_state["understanding"] is not None
    assert "reasoning" in final_state["required_capabilities"]
    assert final_state["selected_agents"]["reasoning"] == "reasoning_agent"
    assert len(final_state["plan"]) > 0
    assert len(final_state["execution_steps"]) > 0
    assert len(final_state["observations"]) > 0
    assert final_state["verification_results"]["is_verified"] is True
    assert final_state["final_result"] is not None
    assert final_state["final_result"]["status"] == "COMPLETED"
    assert len(final_state["final_result"]["outputs"]["key_points"]) == 3

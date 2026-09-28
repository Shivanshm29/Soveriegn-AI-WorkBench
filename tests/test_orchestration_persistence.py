"""Test M: State Persistence and Event Emission during Graph Execution."""

import pytest
from pathlib import Path
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.orchestration.graph import WorkbenchOrchestrator


def test_orchestration_persists_to_state_store_and_emits_events(tmp_path: Path):
    """Verify orchestrator syncs state and events to LocalStateStore at checkpoints."""
    store = LocalStateStore(base_dir=tmp_path / "orch_state")
    orchestrator = WorkbenchOrchestrator(state_store=store)

    orchestrator.nodes.agent_executor.register_handler(
        "reasoning_agent",
        lambda step, ctx: {"summary": "Persisted analysis"},
    )

    final_state = orchestrator.run("Audit local records", task_id="persist-orch-1")
    assert final_state["task_status"] == TaskStatus.COMPLETED.value

    # Load from store
    loaded_task = store.load_task("persist-orch-1")
    assert loaded_task is not None
    assert loaded_task.task_id == "persist-orch-1"
    assert loaded_task.status == TaskStatus.COMPLETED
    assert len(loaded_task.steps) > 0
    assert loaded_task.context["final_result"]["status"] == "COMPLETED"

    # Verify events
    events = store.get_events("persist-orch-1")
    event_types = [e.event_type for e in events]
    assert "TASK_CREATED" in event_types
    assert "TASK_STATUS_CHANGED" in event_types
    assert "STEP_STARTED" in event_types
    assert "STEP_COMPLETED" in event_types

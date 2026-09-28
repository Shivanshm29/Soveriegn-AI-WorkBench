"""Tests for crash resilience and restart recovery of LocalStateStore."""

import pytest
from pathlib import Path
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskState, TaskStatus
from backend.app.state.execution_step import ExecutionStep
from backend.app.state.events import TaskEvent, EventType


def test_state_store_persists_across_restart(tmp_path: Path):
    """Verify tasks, steps, and events survive process restart."""
    store_dir = tmp_path / "state_data"

    # 1. Initialize store instance 1
    store1 = LocalStateStore(base_dir=store_dir)

    task = TaskState(task_id="persist-task-1", user_query="Analyze invoice batch")
    task.transition_to(TaskStatus.UNDERSTANDING)
    task.transition_to(TaskStatus.PLANNING)

    step1 = ExecutionStep(
        step_id="step-1",
        task_id="persist-task-1",
        assigned_agent="document_agent",
        action="Extract text",
    )
    step1.start()
    step1.complete({"extracted_text": "Invoice #1024 total $500"})
    task.add_step(step1)

    event1 = TaskEvent(
        task_id="persist-task-1",
        event_type=EventType.STEP_COMPLETED,
        step_id="step-1",
        agent_id="document_agent",
        payload={"pages": 1},
    )
    task.add_event(event1)

    store1.save_task(task)

    # 2. Simulate server restart: create independent store instance pointing to same directory
    store2 = LocalStateStore(base_dir=store_dir)

    # 3. Verify task loaded identically
    loaded = store2.load_task("persist-task-1")
    assert loaded is not None
    assert loaded.task_id == "persist-task-1"
    assert loaded.user_query == "Analyze invoice batch"
    assert loaded.status == TaskStatus.PLANNING
    assert len(loaded.steps) == 1
    assert loaded.steps[0].outputs["extracted_text"] == "Invoice #1024 total $500"
    assert loaded.steps[0].status == "COMPLETED"

    # 4. Verify events retrieved
    events = store2.get_events("persist-task-1")
    assert len(events) >= 1
    assert any(e.event_type == EventType.STEP_COMPLETED for e in events)

    # 5. Verify list_tasks
    task_list = store2.list_tasks()
    assert len(task_list) == 1
    assert task_list[0].task_id == "persist-task-1"

    # 6. Verify continuation after restart
    loaded.transition_to(TaskStatus.EXECUTING)
    store2.save_task(loaded)

    store3 = LocalStateStore(base_dir=store_dir)
    reloaded = store3.load_task("persist-task-1")
    assert reloaded.status == TaskStatus.EXECUTING

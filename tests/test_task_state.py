"""Tests for TaskState schema and basic operations."""

import pytest
from datetime import datetime, timezone
from backend.app.state.task_state import TaskState, TaskStatus
from backend.app.state.execution_step import ExecutionStep
from backend.app.state.events import TaskEvent, EventType


def test_task_state_initialization():
    """Verify default initialization of a TaskState instance."""
    task = TaskState(task_id="task-001", user_query="Analyze financial report")
    assert task.task_id == "task-001"
    assert task.user_query == "Analyze financial report"
    assert task.status == TaskStatus.CREATED
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)
    assert len(task.steps) == 0
    assert len(task.events) == 0
    assert not task.is_terminal()


def test_task_state_is_terminal():
    """Verify terminal detection across all task statuses."""
    task = TaskState(task_id="t-term", user_query="Test")

    non_terminal_statuses = [
        TaskStatus.CREATED,
        TaskStatus.UNDERSTANDING,
        TaskStatus.PLANNING,
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.EXECUTING,
        TaskStatus.VERIFYING,
    ]
    for status in non_terminal_statuses:
        task.status = status
        assert not task.is_terminal(), f"{status} should not be terminal"

    terminal_statuses = [
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ]
    for status in terminal_statuses:
        task.status = status
        assert task.is_terminal(), f"{status} should be terminal"


def test_task_state_steps_and_events():
    """Verify adding steps and events to TaskState."""
    task = TaskState(task_id="task-002", user_query="Process document")

    step = ExecutionStep(
        step_id="step-1",
        task_id="task-002",
        assigned_agent="document_agent",
        action="Extract text",
    )
    task.add_step(step)
    assert len(task.steps) == 1
    assert task.get_step("step-1") == step
    assert task.get_step("non-existent") is None

    event = TaskEvent(
        task_id="task-002",
        event_type=EventType.TASK_CREATED,
        message="Task initialized",
    )
    task.add_event(event)
    assert len(task.events) == 1
    assert task.events[0].event_type == EventType.TASK_CREATED


def test_task_state_serialization_roundtrip():
    """Verify full JSON and dict serialization/deserialization."""
    task = TaskState(
        task_id="task-003",
        user_query="Generate Excel summary",
        context={"project": "Industrial"},
        metadata={"priority": "high"},
    )
    step = ExecutionStep(
        step_id="s1",
        task_id="task-003",
        assigned_agent="data_agent",
        action="Calculate totals",
    )
    step.start()
    step.complete({"result": 42})
    task.add_step(step)

    # To / from dict
    d = task.to_dict()
    assert d["task_id"] == "task-003"
    assert len(d["steps"]) == 1

    restored = TaskState.from_dict(d)
    assert restored.task_id == task.task_id
    assert restored.user_query == task.user_query
    assert restored.steps[0].outputs["result"] == 42
    assert restored.steps[0].status == step.status

    # JSON string roundtrip
    json_str = task.model_dump_json()
    from_json = TaskState.model_validate_json(json_str)
    assert from_json.task_id == task.task_id
    assert len(from_json.steps) == 1

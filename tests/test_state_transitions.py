"""Tests for task state transitions and transition validation."""

import pytest
from backend.app.state.task_state import (
    TaskState,
    TaskStatus,
    InvalidStateTransitionError,
)
from backend.app.state.events import EventType


def test_standard_execution_flow():
    """Verify happy path: CREATED -> UNDERSTANDING -> PLANNING -> EXECUTING -> VERIFYING -> COMPLETED."""
    task = TaskState(task_id="flow-1", user_query="Do work")
    assert task.status == TaskStatus.CREATED

    task.transition_to(TaskStatus.UNDERSTANDING)
    assert task.status == TaskStatus.UNDERSTANDING

    task.transition_to(TaskStatus.PLANNING)
    assert task.status == TaskStatus.PLANNING

    task.transition_to(TaskStatus.EXECUTING)
    assert task.status == TaskStatus.EXECUTING

    task.transition_to(TaskStatus.VERIFYING)
    assert task.status == TaskStatus.VERIFYING

    task.transition_to(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
    assert task.is_terminal()


def test_approval_workflow_transitions():
    """Verify approval path: PLANNING -> WAITING_APPROVAL -> EXECUTING."""
    task = TaskState(task_id="approval-1", user_query="Execute dangerous command")
    task.transition_to(TaskStatus.UNDERSTANDING)
    task.transition_to(TaskStatus.PLANNING)

    task.transition_to(TaskStatus.WAITING_APPROVAL)
    assert task.status == TaskStatus.WAITING_APPROVAL

    task.transition_to(TaskStatus.EXECUTING)
    assert task.status == TaskStatus.EXECUTING


def test_verification_replanning_loop():
    """Verify verification failure leads to replanning: VERIFYING -> PLANNING."""
    task = TaskState(task_id="replan-1", user_query="Fix broken logic")
    task.transition_to(TaskStatus.UNDERSTANDING)
    task.transition_to(TaskStatus.PLANNING)
    task.transition_to(TaskStatus.EXECUTING)
    task.transition_to(TaskStatus.VERIFYING)

    # Verification detects a gap, triggers replanning
    task.transition_to(TaskStatus.PLANNING, reason="Verification tests failed, replanning")
    assert task.status == TaskStatus.PLANNING

    task.transition_to(TaskStatus.EXECUTING)
    task.transition_to(TaskStatus.VERIFYING)
    task.transition_to(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED


def test_invalid_transitions_rejected():
    """Verify illegal transitions raise InvalidStateTransitionError."""
    task = TaskState(task_id="illegal-1", user_query="Illegal transition test")

    # CREATED -> EXECUTING is illegal
    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.EXECUTING)

    # CREATED -> COMPLETED is illegal
    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.COMPLETED)

    # Complete the task
    task.transition_to(TaskStatus.UNDERSTANDING)
    task.transition_to(TaskStatus.PLANNING)
    task.transition_to(TaskStatus.EXECUTING)
    task.transition_to(TaskStatus.VERIFYING)
    task.transition_to(TaskStatus.COMPLETED)

    # Terminal state cannot transition to anything
    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.PLANNING)

    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.CREATED)


def test_failure_records_error_message_and_event():
    """Verify transition to FAILED records error message and status change event."""
    task = TaskState(task_id="fail-1", user_query="Task that fails")
    task.transition_to(TaskStatus.FAILED, reason="Sandbox resource exhausted")

    assert task.status == TaskStatus.FAILED
    assert task.error_message == "Sandbox resource exhausted"
    assert task.is_terminal()

    # Verify event recorded
    assert len(task.events) == 1
    event = task.events[0]
    assert event.event_type == EventType.TASK_STATUS_CHANGED
    assert event.payload["from_status"] == TaskStatus.CREATED.value
    assert event.payload["to_status"] == TaskStatus.FAILED.value
    assert event.payload["reason"] == "Sandbox resource exhausted"

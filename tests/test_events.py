"""Tests for TaskEvent and event types."""

import pytest
from datetime import datetime
from backend.app.state.events import TaskEvent, EventType


def test_all_event_types_present():
    """Verify all 16 architecture lifecycle event types are defined."""
    expected_event_types = [
        "TASK_CREATED",
        "TASK_STATUS_CHANGED",
        "STEP_STARTED",
        "STEP_COMPLETED",
        "STEP_FAILED",
        "STEP_SKIPPED",
        "AGENT_DELEGATED",
        "TOOL_CALLED",
        "TOOL_COMPLETED",
        "TOOL_FAILED",
        "APPROVAL_REQUESTED",
        "APPROVAL_GRANTED",
        "APPROVAL_REJECTED",
        "VERIFICATION_STARTED",
        "VERIFICATION_COMPLETED",
        "TASK_ERROR",
    ]
    for name in expected_event_types:
        assert hasattr(EventType, name), f"EventType missing {name}"
        assert getattr(EventType, name).value == name


def test_task_event_creation():
    """Verify TaskEvent default creation and attributes."""
    event = TaskEvent(
        task_id="t-100",
        event_type=EventType.STEP_STARTED,
        step_id="step-1",
        agent_id="document_agent",
        payload={"action": "extract_tables"},
        message="Document agent started table extraction",
    )
    assert event.task_id == "t-100"
    assert event.event_type == EventType.STEP_STARTED
    assert event.step_id == "step-1"
    assert event.agent_id == "document_agent"
    assert event.payload["action"] == "extract_tables"
    assert len(event.event_id) > 0
    assert isinstance(event.timestamp, datetime)


def test_task_event_serialization():
    """Verify TaskEvent serialization roundtrip."""
    event = TaskEvent(
        task_id="t-101",
        event_type=EventType.TOOL_CALLED,
        agent_id="data_agent",
        payload={"tool": "python_calculation"},
        message="Invoking calculator",
    )
    d = event.to_dict()
    assert d["event_type"] == "TOOL_CALLED"
    assert d["task_id"] == "t-101"

    restored = TaskEvent.from_dict(d)
    assert restored.event_id == event.event_id
    assert restored.event_type == EventType.TOOL_CALLED
    assert restored.payload == event.payload

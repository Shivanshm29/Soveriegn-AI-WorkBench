"""Tests for ExecutionStep lifecycle and status changes."""

import pytest
from datetime import datetime
from backend.app.state.execution_step import ExecutionStep, StepStatus


def test_execution_step_initial_state():
    """Verify default step attributes."""
    step = ExecutionStep(
        step_id="step-001",
        task_id="task-001",
        assigned_agent="knowledge_agent",
        action="Search vector store",
        inputs={"query": "sovereign architecture"},
    )
    assert step.step_id == "step-001"
    assert step.task_id == "task-001"
    assert step.assigned_agent == "knowledge_agent"
    assert step.status == StepStatus.PENDING
    assert step.started_at is None
    assert step.completed_at is None
    assert step.error is None
    assert step.retry_count == 0


def test_execution_step_success_lifecycle():
    """Verify standard execution flow: PENDING -> RUNNING -> COMPLETED."""
    step = ExecutionStep(
        step_id="step-002",
        task_id="task-001",
        assigned_agent="data_agent",
        action="Compute metrics",
    )
    step.start()
    assert step.status == StepStatus.RUNNING
    assert isinstance(step.started_at, datetime)

    step.complete(outputs={"sum": 100, "rows": 10})
    assert step.status == StepStatus.COMPLETED
    assert isinstance(step.completed_at, datetime)
    assert step.outputs["sum"] == 100
    assert step.outputs["rows"] == 10


def test_execution_step_failure_lifecycle():
    """Verify failure flow: PENDING -> RUNNING -> FAILED."""
    step = ExecutionStep(
        step_id="step-003",
        task_id="task-001",
        assigned_agent="coding_agent",
        action="Run unit tests",
    )
    step.start()
    step.fail(error="SyntaxError in generated code")

    assert step.status == StepStatus.FAILED
    assert step.error == "SyntaxError in generated code"
    assert isinstance(step.completed_at, datetime)


def test_execution_step_skip_lifecycle():
    """Verify skipping step."""
    step = ExecutionStep(
        step_id="step-004",
        task_id="task-001",
        assigned_agent="vision_agent",
        action="Process images",
    )
    step.skip(reason="Document contains no images")

    assert step.status == StepStatus.SKIPPED
    assert step.outputs.get("skip_reason") == "Document contains no images"
    assert isinstance(step.completed_at, datetime)


def test_execution_step_serialization():
    """Verify serialization to and from dict."""
    step = ExecutionStep(
        step_id="step-005",
        task_id="task-001",
        assigned_agent="document_agent",
        action="Parse PDF",
    )
    step.start()
    step.complete({"pages": 5})

    data = step.to_dict()
    assert data["step_id"] == "step-005"
    assert data["status"] == "COMPLETED"

    restored = ExecutionStep.from_dict(data)
    assert restored.step_id == step.step_id
    assert restored.status == StepStatus.COMPLETED
    assert restored.outputs["pages"] == 5

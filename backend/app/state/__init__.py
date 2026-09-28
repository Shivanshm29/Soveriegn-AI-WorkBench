"""State management package."""

from backend.app.state.events import EventType, TaskEvent
from backend.app.state.execution_step import StepStatus, ExecutionStep
from backend.app.state.task_state import (
    TaskStatus,
    TaskState,
    ALLOWED_TRANSITIONS,
    InvalidStateTransitionError,
)
from backend.app.state.store import (
    StateStore,
    LocalStateStore,
    StateStoreError,
    TaskNotFoundError,
)

__all__ = [
    "EventType",
    "TaskEvent",
    "StepStatus",
    "ExecutionStep",
    "TaskStatus",
    "TaskState",
    "ALLOWED_TRANSITIONS",
    "InvalidStateTransitionError",
    "StateStore",
    "LocalStateStore",
    "StateStoreError",
    "TaskNotFoundError",
]

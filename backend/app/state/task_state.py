"""Task state and status transitions."""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

from backend.app.state.execution_step import ExecutionStep
from backend.app.state.events import TaskEvent, EventType


class TaskStatus(str, Enum):
    """Lifecycle statuses for workbench tasks."""
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.UNDERSTANDING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.UNDERSTANDING: {
        TaskStatus.PLANNING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.PLANNING: {
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.EXECUTING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.WAITING_APPROVAL: {
        TaskStatus.EXECUTING,
        TaskStatus.PLANNING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.EXECUTING: {
        TaskStatus.VERIFYING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,
        TaskStatus.PLANNING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal task state transition is attempted."""

    def __init__(
        self,
        current_status: TaskStatus,
        target_status: TaskStatus,
        reason: Optional[str] = None,
    ):
        msg = f"Cannot transition task from '{current_status.value}' to '{target_status.value}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.current_status = current_status
        self.target_status = target_status
        self.reason = reason


class TaskState(BaseModel):
    """Encapsulates the full state and history of a user task."""

    task_id: str
    user_query: str
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    steps: List[ExecutionStep] = Field(default_factory=list)
    events: List[TaskEvent] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    def is_terminal(self) -> bool:
        """Check if the current task status is terminal."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    def can_transition_to(self, target_status: TaskStatus) -> bool:
        """Check if transitioning to target_status is permitted by the state machine."""
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        return target_status in allowed

    def transition_to(self, new_status: TaskStatus, reason: Optional[str] = None) -> None:
        """Transition task to a new status or raise InvalidStateTransitionError."""
        if not self.can_transition_to(new_status):
            raise InvalidStateTransitionError(self.status, new_status, reason)

        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

        if new_status == TaskStatus.FAILED and reason:
            self.error_message = reason

        # Record audit event
        self.events.append(
            TaskEvent(
                task_id=self.task_id,
                event_type=EventType.TASK_STATUS_CHANGED,
                payload={
                    "from_status": old_status.value,
                    "to_status": new_status.value,
                    "reason": reason,
                },
                message=f"Transitioned from {old_status.value} to {new_status.value}",
            )
        )

    def add_step(self, step: ExecutionStep) -> None:
        """Append an execution step to the plan."""
        self.steps.append(step)
        self.updated_at = datetime.now(timezone.utc)

    def get_step(self, step_id: str) -> Optional[ExecutionStep]:
        """Find an execution step by its step_id."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def add_event(self, event: TaskEvent) -> None:
        """Append an audit/lifecycle event."""
        self.events.append(event)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to standard dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskState":
        """Instantiate TaskState from dictionary."""
        return cls.model_validate(data)

"""Task lifecycle events."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Lifecycle event types for task tracking."""
    TASK_CREATED = "TASK_CREATED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    STEP_SKIPPED = "STEP_SKIPPED"
    AGENT_DELEGATED = "AGENT_DELEGATED"
    TOOL_CALLED = "TOOL_CALLED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"
    RISK_ASSESSMENT_CREATED = "RISK_ASSESSMENT_CREATED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    TASK_ERROR = "TASK_ERROR"


class TaskEvent(BaseModel):
    """An immutable audit or observability event recorded during task execution."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: Optional[str] = None
    step_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskEvent":
        """Instantiate event from dictionary."""
        return cls.model_validate(data)

"""Execution step schema and lifecycle methods."""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Status lifecycle of a plan execution step."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExecutionStep(BaseModel):
    """A discrete unit of execution within a task plan."""

    step_id: str
    task_id: str
    assigned_agent: str
    action: str
    status: StepStatus = StepStatus.PENDING
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0

    def start(self) -> None:
        """Mark step as running."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, outputs: Optional[Dict[str, Any]] = None) -> None:
        """Mark step as successfully completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if outputs:
            self.outputs.update(outputs)

    def fail(self, error: str) -> None:
        """Mark step as failed with an error message."""
        self.status = StepStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error = error

    def skip(self, reason: Optional[str] = None) -> None:
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = datetime.now(timezone.utc)
        if reason:
            self.outputs["skip_reason"] = reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStep":
        """Instantiate step from dictionary."""
        return cls.model_validate(data)

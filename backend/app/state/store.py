"""State persistence store interface and local JSON implementation."""

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union

from backend.app.config.settings import get_settings
from backend.app.state.events import TaskEvent
from backend.app.state.task_state import TaskState, TaskStatus


class StateStoreError(Exception):
    """Base exception for state storage errors."""
    pass


class TaskNotFoundError(StateStoreError):
    """Raised when a specified task ID cannot be found."""
    pass


class StateStore(ABC):
    """Abstract interface for task state persistence."""

    @abstractmethod
    def save_task(self, task: TaskState) -> None:
        """Persist or update a task state."""
        pass

    @abstractmethod
    def load_task(self, task_id: str) -> Optional[TaskState]:
        """Retrieve a task state by ID, or None if not found."""
        pass

    def get_task(self, task_id: str) -> Optional[TaskState]:
        """Retrieve a task state by ID (convenience alias for load_task)."""
        return self.load_task(task_id)

    @abstractmethod
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskState]:
        """List tasks, optionally filtered by status."""
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its associated records."""
        pass

    @abstractmethod
    def record_event(self, event: TaskEvent) -> None:
        """Record an immutable lifecycle/audit event."""
        pass

    @abstractmethod
    def get_events(self, task_id: str) -> List[TaskEvent]:
        """Retrieve all events recorded for a given task."""
        pass


class LocalStateStore(StateStore):
    """Local filesystem state store providing atomic writes and crash-resilient persistence."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir is None:
            settings = get_settings()
            self.base_dir = Path(settings.DATA_ROOT) / "state"
        else:
            self.base_dir = Path(base_dir)

        self.tasks_dir = self.base_dir / "tasks"
        self.events_dir = self.base_dir / "events"

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create required storage directories."""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def _task_path(self, task_id: str) -> Path:
        """Get file path for a task state."""
        return self.tasks_dir / f"{task_id}.json"

    def _events_path(self, task_id: str) -> Path:
        """Get file path for an event log."""
        return self.events_dir / f"{task_id}.jsonl"

    def save_task(self, task: TaskState) -> None:
        """Persist a task state using atomic file replacement."""
        self._ensure_directories()
        target_path = self._task_path(task.task_id)

        try:
            # Atomic write: write to temp file in same directory then os.replace
            content = task.model_dump_json(indent=2)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(self.tasks_dir), prefix=f"{task.task_id}_", suffix=".tmp"
            )
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, str(target_path))

            # Also ensure events are mirrored to the append-only event log
            if task.events:
                self._sync_task_events(task.task_id, task.events)

        except Exception as e:
            raise StateStoreError(f"Failed to persist task '{task.task_id}': {e}") from e

    def _sync_task_events(self, task_id: str, events: List[TaskEvent]) -> None:
        """Synchronize events to append-only log without duplicating existing ones."""
        events_path = self._events_path(task_id)
        existing_ids = set()

        if events_path.exists():
            with open(events_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                            if "event_id" in item:
                                existing_ids.add(item["event_id"])
                        except Exception:
                            continue

        with open(events_path, "a", encoding="utf-8") as f:
            for event in events:
                if event.event_id not in existing_ids:
                    f.write(event.model_dump_json() + "\n")
                    existing_ids.add(event.event_id)

    def load_task(self, task_id: str) -> Optional[TaskState]:
        """Load task state from JSON file."""
        task_path = self._task_path(task_id)
        if not task_path.exists():
            return None

        try:
            content = task_path.read_text(encoding="utf-8")
            return TaskState.model_validate_json(content)
        except Exception as e:
            raise StateStoreError(f"Failed to load task '{task_id}': {e}") from e

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskState]:
        """List tasks ordered by created_at descending."""
        self._ensure_directories()
        tasks: List[TaskState] = []

        for p in self.tasks_dir.glob("*.json"):
            try:
                content = p.read_text(encoding="utf-8")
                task = TaskState.model_validate_json(content)
                if status is None or task.status == status:
                    tasks.append(task)
            except Exception:
                continue

        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def delete_task(self, task_id: str) -> bool:
        """Delete task file and associated event log."""
        task_path = self._task_path(task_id)
        events_path = self._events_path(task_id)

        existed = False
        if task_path.exists():
            task_path.unlink()
            existed = True

        if events_path.exists():
            events_path.unlink()
            existed = True

        return existed

    def record_event(self, event: TaskEvent) -> None:
        """Append an event to the task's JSONL event log."""
        self._ensure_directories()
        events_path = self._events_path(event.task_id)

        try:
            with open(events_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
                f.flush()

            # If task exists, update task state's events array
            task = self.load_task(event.task_id)
            if task:
                if not any(e.event_id == event.event_id for e in task.events):
                    task.events.append(event)
                    self.save_task(task)
        except Exception as e:
            raise StateStoreError(f"Failed to record event '{event.event_id}': {e}") from e

    def get_events(self, task_id: str) -> List[TaskEvent]:
        """Retrieve all events recorded for a task."""
        events_path = self._events_path(task_id)
        if events_path.exists():
            events: List[TaskEvent] = []
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            events.append(TaskEvent.model_validate_json(line))
                return events
            except Exception as e:
                raise StateStoreError(f"Failed to read events for task '{task_id}': {e}") from e

        # Fallback to task state file if events log does not exist
        task = self.load_task(task_id)
        if task:
            return task.events

        return []

    def clear(self) -> None:
        """Clear all tasks and events (primarily for testing)."""
        if self.tasks_dir.exists():
            for p in self.tasks_dir.glob("*.json"):
                p.unlink(missing_ok=True)
            for p in self.tasks_dir.glob("*.tmp"):
                p.unlink(missing_ok=True)
        if self.events_dir.exists():
            for p in self.events_dir.glob("*.jsonl"):
                p.unlink(missing_ok=True)


class InMemoryStateStore(StateStore):
    """In-memory state store useful for fast, isolated test runs and transient tasks."""

    def __init__(self):
        self._tasks: dict = {}
        self._events: dict = {}

    def save_task(self, task: TaskState) -> None:
        self._tasks[task.task_id] = task.model_copy(deep=True)

    def load_task(self, task_id: str) -> Optional[TaskState]:
        t = self._tasks.get(task_id)
        return t.model_copy(deep=True) if t else None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskState]:
        res = list(self._tasks.values())
        if status is not None:
            res = [t for t in res if t.status == status]
        res.sort(key=lambda t: t.created_at, reverse=True)
        return res

    def delete_task(self, task_id: str) -> bool:
        existed = task_id in self._tasks
        self._tasks.pop(task_id, None)
        self._events.pop(task_id, None)
        return existed

    def record_event(self, event: TaskEvent) -> None:
        if event.task_id not in self._events:
            self._events[event.task_id] = []
        self._events[event.task_id].append(event)
        if event.task_id in self._tasks:
            t = self._tasks[event.task_id]
            if not any(e.event_id == event.event_id for e in t.events):
                t.events.append(event)

    def get_events(self, task_id: str) -> List[TaskEvent]:
        return list(self._events.get(task_id, []))

    def clear(self) -> None:
        self._tasks.clear()
        self._events.clear()


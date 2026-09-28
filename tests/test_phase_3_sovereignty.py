"""Tests verifying zero external egress during Phase 3 registry and state operations."""

import socket
import pytest
from unittest.mock import patch
from pathlib import Path

from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.schemas.snapshot import get_registry_snapshot
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskState, TaskStatus
from backend.app.state.execution_step import ExecutionStep
from backend.app.agents.a2a import create_a2a_request, A2AMessageValidator


def test_phase_3_registries_and_state_make_zero_network_calls(tmp_path: Path):
    """Verify that all Phase 3 operations execute strictly locally without network calls."""

    # Intercept socket creation to ensure no network calls happen
    with patch.object(socket, "socket", side_effect=RuntimeError("Unexpected network socket access")):
        # 1. Model Registry
        model_reg = ModelRegistry()
        assert len(model_reg.list()) > 0
        model_reg.find_by_capability("reasoning")

        # 2. Agent Registry
        agent_reg = AgentRegistry()
        assert len(agent_reg.list()) == 7
        agent_reg.find_by_capability("visual_reasoning")

        # 3. Tool Registry
        tool_reg = ToolRegistry()
        assert len(tool_reg.list()) == 8
        tool_reg.find_by_capability("calculation")

        # 4. Snapshot
        snapshot = get_registry_snapshot(model_reg, agent_reg, tool_reg)
        assert snapshot.sovereign_mode is True
        assert snapshot.model_count > 0
        assert snapshot.agent_count == 7
        assert snapshot.tool_count == 8

        # 5. State Store
        store = LocalStateStore(base_dir=tmp_path / "state")
        task = TaskState(task_id="sovereign-task-1", user_query="Local audit")
        task.transition_to(TaskStatus.UNDERSTANDING)
        task.transition_to(TaskStatus.PLANNING)
        step = ExecutionStep(
            step_id="step-1",
            task_id="sovereign-task-1",
            assigned_agent="knowledge_agent",
            action="Local retrieval",
        )
        step.start()
        step.complete({"status": "ok"})
        task.add_step(step)
        store.save_task(task)

        loaded = store.load_task("sovereign-task-1")
        assert loaded is not None
        assert loaded.task_id == "sovereign-task-1"

        # 6. A2A messaging
        msg = create_a2a_request(
            task_id="sovereign-task-1",
            sender="main_agent",
            receiver="reasoning_agent",
            payload={"goal": "verify air-gap"},
            requested_capabilities=["reasoning"],
        )
        A2AMessageValidator.validate(msg, agent_registry=agent_reg)

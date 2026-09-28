"""Phase 3 Acceptance Test Suite — Registries, State Management, and A2A Messaging.

Verifies all 17 Phase 3 acceptance criteria against the project contract.
"""

import socket
import pytest
from pathlib import Path
from unittest.mock import patch

from backend.app.config.settings import get_settings
from backend.app.schemas.models import ModelDefinition
from backend.app.models.registry import (
    ModelRegistry,
    DuplicateModelError,
    UnknownModelError,
)
from backend.app.schemas.agents import AgentContract
from backend.app.agents.registry import (
    AgentRegistry,
    DuplicateAgentError,
    UnknownAgentError,
)
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import (
    ToolRegistry,
    DuplicateToolError,
    UnknownToolError,
)
from backend.app.schemas.snapshot import get_registry_snapshot
from backend.app.state.task_state import (
    TaskState,
    TaskStatus,
    InvalidStateTransitionError,
)
from backend.app.state.execution_step import ExecutionStep, StepStatus
from backend.app.state.events import TaskEvent, EventType
from backend.app.state.store import LocalStateStore
from backend.app.agents.a2a import (
    A2AMessageValidator,
    InvalidA2AMessageError,
    create_a2a_request,
    create_a2a_response,
)


def test_acceptance_01_phase_0_passes():
    """Acceptance 1: Phase 0 settings and contracts are valid."""
    settings = get_settings()
    assert settings.APP_ENV == "development"
    assert settings.SOVEREIGN_MODE is True


def test_acceptance_02_phase_1_passes():
    """Acceptance 2: Phase 1 local model runtime and registry resolution pass."""
    from backend.app.models.runtime_factory import create_model_runtime
    runtime = create_model_runtime()
    assert runtime is not None


def test_acceptance_03_phase_2_passes():
    """Acceptance 3: Phase 2 sovereignty and zero-egress boundaries are enforced."""
    from backend.app.security.network_policy import NetworkPolicy
    policy = NetworkPolicy()
    assert policy.check_host("127.0.0.1").allowed is True
    assert policy.check_host("api.openai.com").allowed is False



def test_acceptance_04_model_registry_functions():
    """Acceptance 4: ModelRegistry supports register, unregister, get, list, duplicate rejection, and capability discovery."""
    registry = ModelRegistry()
    m = ModelDefinition(
        model_id="test-model-phase3",
        name="Phase 3 Model",
        context_window=16384,
        capabilities=["reasoning", "coding"],
    )
    registry.register(m)
    assert registry.exists("test-model-phase3")
    assert registry.get("test-model-phase3").model_id == "test-model-phase3"

    with pytest.raises(DuplicateModelError):
        registry.register(m)

    found = registry.find_by_capability("coding")
    assert any(mod.model_id == "test-model-phase3" for mod in found)

    registry.unregister("test-model-phase3")
    assert not registry.exists("test-model-phase3")


def test_acceptance_05_agent_registry_prepopulated_and_functional():
    """Acceptance 5: AgentRegistry contains the 7 standard agents from AGENTS.md and supports capability lookup."""
    registry = AgentRegistry()
    expected = [
        "main_agent",
        "reasoning_agent",
        "document_agent",
        "vision_agent",
        "knowledge_agent",
        "coding_agent",
        "data_agent",
    ]
    for agent_id in expected:
        assert registry.exists(agent_id), f"Missing expected agent {agent_id}"

    # Capability lookup
    reasoning_agents = registry.find_by_capability("planning")
    assert any(a.agent_id == "reasoning_agent" for a in reasoning_agents)

    vision_agents = registry.find_by_capability("visual_reasoning")
    assert any(a.agent_id == "vision_agent" for a in vision_agents)


def test_acceptance_06_tool_registry_prepopulated_and_functional():
    """Acceptance 6: ToolRegistry contains the 8 standard tools and supports capability and risk lookup."""
    registry = ToolRegistry()
    expected = [
        "file_read",
        "file_write",
        "ocr",
        "knowledge_search",
        "python_calculation",
        "sandbox_execute",
        "create_docx",
        "create_xlsx",
    ]
    for tool_id in expected:
        assert registry.exists(tool_id), f"Missing expected tool {tool_id}"

    # High risk tools lookup
    high_risk = registry.find_by_risk("HIGH")
    assert any(t.tool_id == "sandbox_execute" for t in high_risk)


def test_acceptance_07_task_state_initialized():
    """Acceptance 7: TaskState initializes with status CREATED, timestamps, empty steps and events."""
    task = TaskState(task_id="acc-task-1", user_query="Analyze invoice")
    assert task.status == TaskStatus.CREATED
    assert task.created_at is not None
    assert task.updated_at is not None
    assert len(task.steps) == 0
    assert len(task.events) == 0
    assert not task.is_terminal()


def test_acceptance_08_legal_state_transitions():
    """Acceptance 8: Legal state transitions succeed along the lifecycle path."""
    task = TaskState(task_id="acc-task-2", user_query="Process contract")
    task.transition_to(TaskStatus.UNDERSTANDING)
    task.transition_to(TaskStatus.PLANNING)
    task.transition_to(TaskStatus.EXECUTING)
    task.transition_to(TaskStatus.VERIFYING)
    task.transition_to(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
    assert task.is_terminal()


def test_acceptance_09_illegal_state_transitions_fail_closed():
    """Acceptance 9: Invalid state transitions raise InvalidStateTransitionError and fail closed."""
    task = TaskState(task_id="acc-task-3", user_query="Process contract")
    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        task.transition_to(TaskStatus.EXECUTING)


def test_acceptance_10_terminal_states_prevent_further_transitions():
    """Acceptance 10: Terminal states (COMPLETED, FAILED, CANCELLED) prevent any subsequent transitions."""
    for terminal_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        task = TaskState(task_id=f"acc-term-{terminal_status.value}", user_query="Terminal test")
        task.status = terminal_status
        assert task.is_terminal()
        with pytest.raises(InvalidStateTransitionError):
            task.transition_to(TaskStatus.PLANNING)


def test_acceptance_11_execution_steps_lifecycle():
    """Acceptance 11: ExecutionSteps progress through PENDING -> RUNNING -> COMPLETED/FAILED/SKIPPED."""
    step = ExecutionStep(
        step_id="step-acc-1",
        task_id="acc-task-4",
        assigned_agent="document_agent",
        action="Extract OCR text",
    )
    assert step.status == StepStatus.PENDING
    step.start()
    assert step.status == StepStatus.RUNNING
    step.complete(outputs={"text": "Invoice total: 100"})
    assert step.status == StepStatus.COMPLETED
    assert step.outputs["text"] == "Invoice total: 100"


def test_acceptance_12_event_logging_comprehensive():
    """Acceptance 12: Task events record lifecycle transitions and actions."""
    task = TaskState(task_id="acc-task-5", user_query="Audit logging")
    task.transition_to(TaskStatus.UNDERSTANDING)
    assert len(task.events) == 1
    assert task.events[0].event_type == EventType.TASK_STATUS_CHANGED

    event = TaskEvent(
        task_id="acc-task-5",
        event_type=EventType.TOOL_CALLED,
        agent_id="document_agent",
        payload={"tool": "ocr"},
    )
    task.add_event(event)
    assert len(task.events) == 2


def test_acceptance_13_a2a_contract_enforced():
    """Acceptance 13: Structured A2A message validates sender, receiver, and schema."""
    registry = AgentRegistry()
    msg = create_a2a_request(
        task_id="acc-task-6",
        sender="main_agent",
        receiver="document_agent",
        payload={"doc": "file.pdf"},
    )
    # Valid
    A2AMessageValidator.validate(msg, agent_registry=registry)

    # Self-messaging fails
    msg_self = create_a2a_request(
        task_id="acc-task-6",
        sender="main_agent",
        receiver="main_agent",
    )
    with pytest.raises(InvalidA2AMessageError):
        A2AMessageValidator.validate(msg_self, agent_registry=registry)


def test_acceptance_14_a2a_capability_delegation_rule():
    """Acceptance 14: Delegation verifies receiver has the requested capabilities per AGENTS.md."""
    registry = AgentRegistry()
    # document_agent does NOT declare code_execution
    bad_msg = create_a2a_request(
        task_id="acc-task-7",
        sender="main_agent",
        receiver="document_agent",
        requested_capabilities=["code_execution"],
    )
    with pytest.raises(InvalidA2AMessageError):
        A2AMessageValidator.validate(bad_msg, agent_registry=registry)

    # coding_agent DOES declare code_execution
    good_msg = create_a2a_request(
        task_id="acc-task-7",
        sender="main_agent",
        receiver="coding_agent",
        requested_capabilities=["code_execution"],
    )
    A2AMessageValidator.validate(good_msg, agent_registry=registry)


def test_acceptance_15_local_state_store_persistence(tmp_path: Path):
    """Acceptance 15: State survives restart via LocalStateStore."""
    store_dir = tmp_path / "acc_state"
    store1 = LocalStateStore(base_dir=store_dir)

    task = TaskState(task_id="acc-restart-1", user_query="Restart test")
    task.transition_to(TaskStatus.UNDERSTANDING)
    store1.save_task(task)

    store2 = LocalStateStore(base_dir=store_dir)
    loaded = store2.load_task("acc-restart-1")
    assert loaded is not None
    assert loaded.status == TaskStatus.UNDERSTANDING


def test_acceptance_16_state_store_atomic_writes(tmp_path: Path):
    """Acceptance 16: State store uses atomic writes and leaves no corrupt tmp files on clean save."""
    store_dir = tmp_path / "acc_atomic"
    store = LocalStateStore(base_dir=store_dir)

    task = TaskState(task_id="acc-atomic-1", user_query="Atomic test")
    store.save_task(task)

    # Confirm only .json file exists in tasks_dir, no dangling .tmp files
    tmp_files = list(store.tasks_dir.glob("*.tmp"))
    assert len(tmp_files) == 0
    assert (store.tasks_dir / "acc-atomic-1.json").exists()


def test_acceptance_17_registries_and_state_zero_egress(tmp_path: Path):
    """Acceptance 17: Phase 3 components make zero external calls and operate air-gapped."""
    with patch.object(socket, "socket", side_effect=RuntimeError("Unexpected network egress")):
        model_reg = ModelRegistry()
        agent_reg = AgentRegistry()
        tool_reg = ToolRegistry()
        snapshot = get_registry_snapshot(model_reg, agent_reg, tool_reg)
        assert snapshot.sovereign_mode is True

        store = LocalStateStore(base_dir=tmp_path / "state_egress")
        task = TaskState(task_id="zero-egress-task", user_query="Verify airgap")
        store.save_task(task)
        loaded = store.load_task("zero-egress-task")
        assert loaded is not None

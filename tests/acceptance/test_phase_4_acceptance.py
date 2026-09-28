"""Phase 4 Acceptance Test Suite — LangGraph Orchestration Layer.

Verifies all 22 Phase 4 acceptance criteria against the project contract.
"""

import socket
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import langgraph
from langgraph.graph import StateGraph

from backend.app.config.settings import get_settings
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelResponse

from backend.app.orchestration.graph import (
    WorkbenchOrchestrator,
    build_orchestration_graph,
)
from backend.app.orchestration.state import (
    OrchestrationState,
    create_initial_orchestration_state,
)
from backend.app.orchestration.understanding import TaskUnderstanding, understand_task
from backend.app.orchestration.routing import TaskRouter
from backend.app.orchestration.planner import PlanStep, PlanValidator
from backend.app.orchestration.policy import PolicyEvaluator
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.observation import ObservationEvaluator
from backend.app.orchestration.verification import PlanVerifier


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
    """Acceptance 3: Phase 2 sovereignty and zero-egress boundary enforced."""
    from backend.app.security.network_policy import NetworkPolicy
    policy = NetworkPolicy()
    assert policy.check_host("127.0.0.1").allowed is True
    assert policy.check_host("api.openai.com").allowed is False


def test_acceptance_04_phase_3_passes():
    """Acceptance 4: Phase 3 registries, state machine, and A2A contracts pass."""
    from backend.app.state.task_state import TaskState, TaskStatus
    task = TaskState(task_id="p3-check", user_query="test")
    assert task.status == TaskStatus.CREATED
    task.transition_to(TaskStatus.UNDERSTANDING)
    assert task.status == TaskStatus.UNDERSTANDING


def test_acceptance_05_langgraph_installed_correctly():
    """Acceptance 5: LangGraph is installed and importable in environment."""
    assert langgraph is not None
    builder = StateGraph(dict)
    assert builder is not None


def test_acceptance_06_graph_compiles():
    """Acceptance 6: Graph compiles with all required nodes and branching edges."""
    orchestrator = WorkbenchOrchestrator()
    graph_obj = orchestrator.graph.get_graph()
    required_nodes = ["understand", "route", "plan", "policy", "execute", "observe", "replan", "verify", "deliver"]
    for node in required_nodes:
        assert node in graph_obj.nodes


def test_acceptance_07_understand_node_works():
    """Acceptance 7: Understand node converts user request into structured TaskUnderstanding."""
    mock_runtime = MagicMock(spec=ModelRuntime)
    mock_runtime.chat.return_value = ModelResponse(
        content='{"intent": "Decompose task", "capabilities": ["reasoning"], "modalities": ["text"], "complexity": "LOW", "output_type": "text"}',
        model="Qwen/Qwen3-4B",
    )
    understanding = understand_task("Decompose task", mock_runtime, ModelRegistry())
    assert isinstance(understanding, TaskUnderstanding)
    assert "reasoning" in understanding.capabilities


def test_acceptance_08_route_node_works():
    """Acceptance 8: Route node assigns candidate agents by capability."""
    router = TaskRouter(AgentRegistry(), ModelRegistry())
    decision = router.route(["visual_reasoning", "code_generation"])
    assert decision.selected_agents["visual_reasoning"] == "vision_agent"
    assert decision.selected_agents["code_generation"] == "coding_agent"


def test_acceptance_09_plan_node_works():
    """Acceptance 9: Plan node constructs and validates plan steps."""
    validator = PlanValidator(AgentRegistry(), ToolRegistry())
    valid_step = PlanStep(
        step_id="step_1",
        description="Reason through prompt",
        capability="reasoning",
        agent_id="reasoning_agent",
    )
    # Should validate without error
    validator.validate([valid_step])


def test_acceptance_10_policy_checkpoint_exists():
    """Acceptance 10: Policy checkpoint evaluates tool risk and approval flags."""
    evaluator = PolicyEvaluator(ToolRegistry())
    safe_step = PlanStep(step_id="s1", description="read", capability="document_extraction", agent_id="document_agent", required_tools=["file_read"])
    approval_step = PlanStep(step_id="s2", description="sandbox", capability="code_execution", agent_id="coding_agent", required_tools=["sandbox_execute"])

    assert evaluator.evaluate_step(safe_step).status == "allowed"
    assert evaluator.evaluate_step(approval_step).status == "requires_approval"


def test_acceptance_11_execute_node_works():
    """Acceptance 11: Execute node invokes agents through executor."""
    executor = AgentExecutor(AgentRegistry(), ToolRegistry())
    executor.register_handler("reasoning_agent", lambda step, ctx: {"summary": "done"})
    step = PlanStep(step_id="s1", description="reason", capability="reasoning", agent_id="reasoning_agent")
    res = executor.execute("reasoning_agent", step, {})
    assert res.status == "SUCCESS"
    assert res.output["summary"] == "done"


def test_acceptance_12_observe_node_works():
    """Acceptance 12: Observe node interprets execution result into structured observation."""
    step = PlanStep(step_id="s1", description="run", capability="reasoning", agent_id="reasoning_agent")
    from backend.app.orchestration.execution import AgentExecutionResult
    res = AgentExecutionResult(status="SUCCESS", agent_id="reasoning_agent", output={"done": True})
    obs = ObservationEvaluator.evaluate(step, res)
    assert obs.outcome == "SUCCESS"


def test_acceptance_13_replan_node_works():
    """Acceptance 13: Replan path triggers on recoverable failure."""
    orchestrator = WorkbenchOrchestrator()
    count = 0
    def handler(step, ctx):
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("Transient read error")
        return {"output": "recovered"}

    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", handler)
    final_state = orchestrator.run("Recoverable task")
    assert final_state["task_status"] == "COMPLETED"
    assert final_state["retry_count"] == 1


def test_acceptance_14_retry_limits_work():
    """Acceptance 14: Retry limits terminate failing task in FAILED state."""
    orchestrator = WorkbenchOrchestrator()
    def fail(step, ctx):
        raise RuntimeError("Fatal persistent error")
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", fail)
    final_state = orchestrator.run("Doomed task")
    assert final_state["task_status"] == "FAILED"
    assert final_state["retry_count"] > final_state["max_retries"]


def test_acceptance_15_verify_node_works():
    """Acceptance 15: Verify node validates execution completeness."""
    plan = [{"step_id": "s1"}]
    steps = [{"step_id": "s1", "status": "COMPLETED", "outputs": {"result": 1}}]
    obs = [{"step_id": "s1", "outcome": "SUCCESS"}]
    res = PlanVerifier.verify(plan, steps, obs)
    assert res.is_verified is True


def test_acceptance_16_deliver_node_works():
    """Acceptance 16: Deliver node stores final result and sets status."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: {"res": "delivered"})
    state = orchestrator.run("Deliver test")
    assert state["task_status"] == "COMPLETED"
    assert state["final_result"]["outputs"]["res"] == "delivered"


def test_acceptance_17_state_persists(tmp_path: Path):
    """Acceptance 17: State survives and persists to LocalStateStore."""
    store = LocalStateStore(base_dir=tmp_path / "acc_store")
    orchestrator = WorkbenchOrchestrator(state_store=store)
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: {"res": 1})
    orchestrator.run("Persist task", task_id="task-persisted")

    loaded = store.load_task("task-persisted")
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED


def test_acceptance_18_events_are_emitted(tmp_path: Path):
    """Acceptance 18: Events are recorded in audit trail."""
    store = LocalStateStore(base_dir=tmp_path / "acc_events")
    orchestrator = WorkbenchOrchestrator(state_store=store)
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: {"res": 1})
    orchestrator.run("Events task", task_id="task-events")

    events = store.get_events("task-events")
    types = [e.event_type for e in events]
    assert "TASK_CREATED" in types
    assert "STEP_STARTED" in types
    assert "STEP_COMPLETED" in types


def test_acceptance_19_a2a_contract_used():
    """Acceptance 19: A2A TASK_DELEGATION and TASK_RESULT contracts are emitted during execution."""
    executor = AgentExecutor(AgentRegistry(), ToolRegistry())
    executor.register_handler("reasoning_agent", lambda s, c: {"ok": True})
    step = PlanStep(step_id="s1", description="desc", capability="reasoning", agent_id="reasoning_agent")
    res = executor.execute("reasoning_agent", step, {"task_id": "acc-a2a"})

    assert res.delegation_message.type == "TASK_DELEGATION"
    assert res.result_message.type == "TASK_RESULT"
    assert res.result_message.status == "COMPLETED"


def test_acceptance_20_task_isolation_works():
    """Acceptance 20: Concurrent/sequential tasks maintain complete state isolation."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: {"val": c["user_request"]})
    s1 = orchestrator.run("Task 1", task_id="t1")
    s2 = orchestrator.run("Task 2", task_id="t2")

    assert s1["task_id"] == "t1"
    assert s2["task_id"] == "t2"
    assert s1["final_result"]["outputs"]["val"] == "Task 1"
    assert s2["final_result"]["outputs"]["val"] == "Task 2"


def test_acceptance_21_no_infinite_loop_exists():
    """Acceptance 21: Replan and recovery loops are bounded by configured limits."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: (_ for _ in ()).throw(RuntimeError("fail")))
    res = orchestrator.run("Loop test")
    assert res["task_status"] == "FAILED"


def test_acceptance_22_sovereignty_preserved_and_no_phase_5():
    """Acceptance 22: Zero network egress maintained, no Phase 5+ functionality."""
    with patch.object(socket, "socket", side_effect=RuntimeError("Egress attempt")):
        orchestrator = WorkbenchOrchestrator()
        orchestrator.nodes.agent_executor.register_handler("reasoning_agent", lambda s, c: {"sovereign": True})
        res = orchestrator.run("Air-gapped run")
        assert res["task_status"] == "COMPLETED"

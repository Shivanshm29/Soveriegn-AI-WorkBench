"""Orchestration state definition and synchronization with Phase 3 persistence."""

import uuid
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timezone

from backend.app.config.settings import get_settings
from backend.app.state.task_state import TaskState, TaskStatus
from backend.app.state.execution_step import ExecutionStep, StepStatus
from backend.app.state.events import TaskEvent, EventType
from backend.app.state.store import StateStore


class OrchestrationState(TypedDict, total=False):
    """LangGraph execution state dictionary."""

    task_id: str
    user_request: str
    task_status: str
    data_sensitivity: str
    understanding: Optional[Dict[str, Any]]
    required_capabilities: List[str]
    selected_agents: Dict[str, str]
    selected_models: Dict[str, str]
    plan: List[Dict[str, Any]]
    current_step_index: int
    execution_steps: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    errors: List[str]
    verification_results: Dict[str, Any]
    retry_count: int
    max_retries: int
    step_count: int
    max_agent_steps: int
    final_result: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    policy_decision: Optional[Dict[str, Any]]
    approval_request: Optional[Dict[str, Any]]
    approval_decision: Optional[Dict[str, Any]]
    last_execution_result: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


def create_initial_orchestration_state(
    task_id: Optional[str] = None,
    user_request: str = "",
    data_sensitivity: str = "INTERNAL",
    metadata: Optional[Dict[str, Any]] = None,
) -> OrchestrationState:
    """Create a clean, isolated orchestration state for a new task."""
    settings = get_settings()
    tid = task_id or str(uuid.uuid4())

    return OrchestrationState(
        task_id=tid,
        user_request=user_request,
        task_status=TaskStatus.CREATED.value,
        data_sensitivity=data_sensitivity,
        understanding=None,
        required_capabilities=[],
        selected_agents={},
        selected_models={},
        plan=[],
        current_step_index=0,
        execution_steps=[],
        observations=[],
        errors=[],
        verification_results={},
        retry_count=0,
        max_retries=settings.MAX_RETRIES,
        step_count=0,
        max_agent_steps=settings.MAX_AGENT_STEPS,
        final_result=None,
        risk_assessment=None,
        policy_decision=None,
        approval_request=None,
        approval_decision=None,
        last_execution_result=None,
        metadata=metadata or {},
    )



def state_from_task_state(task: TaskState) -> OrchestrationState:
    """Bridge Phase 3 TaskState into LangGraph OrchestrationState."""
    settings = get_settings()
    return OrchestrationState(
        task_id=task.task_id,
        user_request=task.user_query,
        task_status=task.status.value,
        data_sensitivity=task.context.get("data_sensitivity", "INTERNAL"),
        understanding=task.context.get("understanding"),
        required_capabilities=task.context.get("required_capabilities", []),
        selected_agents=task.context.get("selected_agents", {}),
        selected_models=task.context.get("selected_models", {}),
        plan=task.context.get("plan", []),
        current_step_index=task.context.get("current_step_index", 0),
        execution_steps=[step.to_dict() for step in task.steps],
        observations=task.context.get("observations", []),
        errors=[task.error_message] if task.error_message else [],
        verification_results=task.context.get("verification_results", {}),
        retry_count=task.context.get("retry_count", 0),
        max_retries=settings.MAX_RETRIES,
        step_count=len(task.steps),
        max_agent_steps=settings.MAX_AGENT_STEPS,
        final_result=task.context.get("final_result"),
        risk_assessment=task.context.get("risk_assessment"),
        policy_decision=task.context.get("policy_decision"),
        approval_request=task.context.get("approval_request"),
        approval_decision=task.context.get("approval_decision"),
        metadata=dict(task.metadata),
    )


def sync_orchestration_to_task_state(
    state: OrchestrationState,
    store: Optional[StateStore] = None,
) -> TaskState:
    """Synchronize OrchestrationState back to Phase 3 TaskState and persist if store is provided."""
    status_str = state.get("task_status", TaskStatus.CREATED.value)
    try:
        status_enum = TaskStatus(status_str)
    except ValueError:
        status_enum = TaskStatus.FAILED

    steps: List[ExecutionStep] = []
    for s_dict in state.get("execution_steps", []):
        steps.append(ExecutionStep.from_dict(s_dict))

    task = TaskState(
        task_id=state["task_id"],
        user_query=state.get("user_request", ""),
        status=status_enum,
        steps=steps,
        context={
            "data_sensitivity": state.get("data_sensitivity", "INTERNAL"),
            "understanding": state.get("understanding"),
            "required_capabilities": state.get("required_capabilities", []),
            "selected_agents": state.get("selected_agents", {}),
            "selected_models": state.get("selected_models", {}),
            "plan": state.get("plan", []),
            "current_step_index": state.get("current_step_index", 0),
            "observations": state.get("observations", []),
            "verification_results": state.get("verification_results", {}),
            "retry_count": state.get("retry_count", 0),
            "final_result": state.get("final_result"),
            "risk_assessment": state.get("risk_assessment"),
            "policy_decision": state.get("policy_decision"),
            "approval_request": state.get("approval_request"),
            "approval_decision": state.get("approval_decision"),
        },
        metadata=state.get("metadata", {}),
        error_message=state["errors"][-1] if state.get("errors") else None,
    )

    if store is not None:
        store.save_task(task)

    return task

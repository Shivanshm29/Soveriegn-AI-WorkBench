"""LangGraph StateGraph builder, edge logic, and compilation for Workbench Orchestrator."""

from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, START, END

from backend.app.models.registry import ModelRegistry
from backend.app.models.runtime import ModelRuntime
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import StateStore
from backend.app.state.task_state import TaskStatus
from backend.app.orchestration.state import (
    OrchestrationState,
    create_initial_orchestration_state,
)
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.nodes import OrchestrationNodes


def route_after_observe(state: OrchestrationState) -> str:
    """Route from OBSERVE based on status."""
    status = state.get("task_status")
    if status == TaskStatus.FAILED.value:
        return "deliver"
    if status == "REPLAN":
        return "replan"
    if status == TaskStatus.VERIFYING.value:
        return "verify"
    return "execute"


def route_after_replan(state: OrchestrationState) -> str:
    """Route from REPLAN: if limit exceeded, go to deliver; else execute."""
    if state.get("task_status") == TaskStatus.FAILED.value:
        return "deliver"
    return "execute"


def route_after_policy(state: OrchestrationState) -> str:
    """Route from POLICY: if waiting approval or fatal policy denial, deliver; else execute."""
    status = state.get("task_status")
    if status in (TaskStatus.WAITING_APPROVAL.value, TaskStatus.FAILED.value):
        return "deliver"
    return "execute"


def route_after_verify(state: OrchestrationState) -> str:
    """Route from VERIFY: if verified, deliver; if failed and retry available, replan."""
    if state.get("task_status") == "REPLAN":
        return "replan"
    return "deliver"


def build_orchestration_graph(nodes: OrchestrationNodes):
    """Build and compile the complete workbench LangGraph state machine."""
    builder = StateGraph(OrchestrationState)

    # Register all lifecycle nodes
    builder.add_node("understand", nodes.understand_node)
    builder.add_node("route", nodes.route_node)
    builder.add_node("plan", nodes.plan_node)
    builder.add_node("policy", nodes.policy_node)
    builder.add_node("execute", nodes.execute_node)
    builder.add_node("observe", nodes.observe_node)
    builder.add_node("replan", nodes.replan_node)
    builder.add_node("verify", nodes.verify_node)
    builder.add_node("deliver", nodes.deliver_node)

    # Sequential edges
    builder.add_edge(START, "understand")
    builder.add_edge("understand", "route")
    builder.add_edge("route", "plan")
    builder.add_edge("plan", "policy")

    # Conditional branching from policy: allows execution or pauses/delivers on approval/denial
    builder.add_conditional_edges(
        "policy",
        route_after_policy,
        {
            "execute": "execute",
            "deliver": "deliver",
        },
    )

    builder.add_edge("execute", "observe")

    # Conditional branching
    builder.add_conditional_edges(
        "observe",
        route_after_observe,
        {
            "deliver": "deliver",
            "replan": "replan",
            "verify": "verify",
            "execute": "execute",
        },
    )

    builder.add_conditional_edges(
        "replan",
        route_after_replan,
        {
            "deliver": "deliver",
            "execute": "execute",
        },
    )

    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "deliver": "deliver",
            "replan": "replan",
        },
    )

    builder.add_edge("deliver", END)

    return builder.compile()


class WorkbenchOrchestrator:
    """High-level orchestrator executing workbench user tasks through compiled LangGraph."""

    def __init__(
        self,
        model_registry: Optional[ModelRegistry] = None,
        agent_registry: Optional[AgentRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        model_runtime: Optional[ModelRuntime] = None,
        agent_executor: Optional[AgentExecutor] = None,
        state_store: Optional[StateStore] = None,
    ):
        self.model_registry = model_registry or ModelRegistry()
        self.agent_registry = agent_registry or AgentRegistry()
        self.tool_registry = tool_registry or ToolRegistry()
        self.model_runtime = model_runtime
        self.state_store = state_store

        self.nodes = OrchestrationNodes(
            model_registry=self.model_registry,
            agent_registry=self.agent_registry,
            tool_registry=self.tool_registry,
            model_runtime=self.model_runtime,
            agent_executor=agent_executor,
            state_store=self.state_store,
        )
        self.graph = build_orchestration_graph(self.nodes)

    def run(
        self,
        user_request: str,
        task_id: Optional[str] = None,
        data_sensitivity: str = "INTERNAL",
        metadata: Optional[Dict[str, Any]] = None,
        initial_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> OrchestrationState:
        """Execute a user task to completion or approval pause through the compiled state graph."""
        combined_metadata = dict(metadata or {})
        if initial_context:
            combined_metadata.update(initial_context)
        if kwargs:
            combined_metadata.update(kwargs)

        initial_state = create_initial_orchestration_state(
            task_id=task_id,
            user_request=user_request,
            data_sensitivity=data_sensitivity,
            metadata=combined_metadata,
        )
        if initial_context:
            initial_state.update(initial_context)
        final_state = self.graph.invoke(initial_state)
        return final_state

    def submit_approval(
        self,
        task_id: str,
        decision: Any,
    ) -> OrchestrationState:
        """Submit a human approval decision for a paused WAITING_APPROVAL task and resume execution."""
        from backend.app.orchestration.state import state_from_task_state
        if not self.state_store:
            raise ValueError("StateStore must be configured to resume paused tasks with approval.")

        task_record = self.state_store.get_task(task_id)
        if not task_record:
            raise ValueError(f"Task '{task_id}' not found in state store.")

        state = state_from_task_state(task_record)
        state["approval_decision"] = decision.to_dict() if hasattr(decision, "to_dict") else dict(decision)

        # Re-invoke graph; the policy node evaluates the decision and transitions to EXECUTING or FAILED
        final_state = self.graph.invoke(state)
        return final_state

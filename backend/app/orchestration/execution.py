"""Agent execution mechanism and A2A delegation integration."""

import uuid
from typing import Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field

from backend.app.agents.registry import AgentRegistry, UnknownAgentError
from backend.app.tools.registry import ToolRegistry
from backend.app.schemas.agents import A2AMessage
from backend.app.agents.a2a import A2AMessageValidator
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.errors import (
    StepExecutionError,
    AgentNotImplementedError,
)


class AgentExecutionResult(BaseModel):
    """Structured outcome of an agent step execution."""

    status: Literal["SUCCESS", "FAILED", "NOT_IMPLEMENTED"]
    agent_id: str = "agent"
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    delegation_message: Optional[A2AMessage] = None
    result_message: Optional[A2AMessage] = None
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return self.model_dump(mode="json")


class AgentExecutor:
    """Invokes specialist agents via Phase 3 registry, enforcing capability and A2A contracts."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model_runtime: Optional[ModelRuntime] = None,
    ):
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.model_runtime = model_runtime
        self._handlers: Dict[str, Callable[[PlanStep, Dict[str, Any]], Dict[str, Any]]] = {}

    def register_handler(
        self,
        key: str,
        handler: Callable[[PlanStep, Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """Register a handler for a specific agent ID or capability (used for real agents or test doubles)."""
        self._handlers[key] = handler

    def execute(
        self,
        agent_id: str,
        step: PlanStep,
        task_context: Dict[str, Any],
    ) -> AgentExecutionResult:
        """Execute a plan step using the assigned agent."""
        task_id = task_context.get("task_id", str(uuid.uuid4()))

        # 1. Validate agent exists and is enabled
        if not self.agent_registry.exists(agent_id):
            raise UnknownAgentError(f"Cannot execute step with unregistered agent '{agent_id}'.")

        agent = self.agent_registry.get(agent_id)
        if not agent.enabled:
            raise StepExecutionError(f"Agent '{agent_id}' is disabled.")

        # 2. Validate agent possesses capability
        if step.capability not in agent.capabilities:
            raise StepExecutionError(
                f"Agent '{agent_id}' does not support required capability '{step.capability}'."
            )

        # 3. Create structured A2A TASK_DELEGATION message
        delegation_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            sender="main_agent",
            receiver=agent_id,
            type="TASK_DELEGATION",
            payload={
                "step_id": step.step_id,
                "action": step.description,
                "capability": step.capability,
                "required_tools": step.required_tools,
                "context": task_context.get("user_request", ""),
            },
            requested_capabilities=[step.capability],
            status="PENDING",
        )
        A2AMessageValidator.validate(delegation_msg, agent_registry=self.agent_registry)

        # 4. Check for registered handler (test double or real specialist implementation)
        if agent_id in self._handlers:
            try:
                output = self._handlers[agent_id](step, task_context)
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=str(e),
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        if step.capability in self._handlers:
            try:
                output = self._handlers[step.capability](step, task_context)
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=str(e),
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 5. Default reasoning agent execution using ModelRuntime if available
        if (
            agent_id in ("main_agent", "reasoning_agent")
            and step.capability in ("reasoning", "structured_reasoning", "planning", "workflow_management")
            and self.model_runtime is not None
        ):
            try:
                prompt = (
                    f"Perform this task step:\n"
                    f"Description: {step.description}\n"
                    f"Context: {task_context.get('user_request', '')}\n"
                    f"Expected Output: {step.expected_output}"
                )
                resp = self.model_runtime.chat(
                    ModelRequest(
                        model=task_context.get("selected_models", {}).get("primary", "Qwen/Qwen3-4B"),
                        messages=[
                            ChatMessage(role="system", content="You are a reasoning agent performing a task step."),
                            ChatMessage(role="user", content=prompt),
                        ],
                        temperature=0.0,
                    )
                )
                output = {"content": resp.content, "step_id": step.step_id}
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"ModelRuntime reasoning execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6. Truthful execution: capability not yet implemented in Phase 4
        not_impl_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            sender=agent_id,
            receiver="main_agent",
            type="TASK_RESULT",
            payload={
                "status": "NOT_IMPLEMENTED",
                "message": f"Agent '{agent_id}' capability '{step.capability}' is not implemented in Phase 4.",
            },
            status="FAILED",
        )
        return AgentExecutionResult(
            status="NOT_IMPLEMENTED",
            agent_id=agent_id,
            error=f"Agent '{agent_id}' capability '{step.capability}' is not implemented in Phase 4.",
            delegation_message=delegation_msg,
            result_message=not_impl_msg,

        )

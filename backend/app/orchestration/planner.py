"""Structured execution planning and DAG/registry plan validation."""

from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.errors import (
    InvalidPlanError,
    UnknownAgentError,
    UnknownToolError,
)


class PlanStep(BaseModel):
    """A discrete, planned step in a task execution plan."""

    step_id: str
    description: str
    capability: str
    agent_id: str
    required_tools: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_output: str = "result"
    verification_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary."""
        return self.model_dump(mode="json")


class PlanValidator:
    """Validates execution plans against AgentRegistry, ToolRegistry, and DAG acyclicity."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
    ):
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry

    def validate(self, steps: List[PlanStep]) -> None:
        """Validate plan structure, agent and tool existence, capabilities, and dependencies."""
        if not steps:
            raise InvalidPlanError("Plan cannot be empty.")

        step_ids: Set[str] = set()
        for idx, step in enumerate(steps):
            if not step.step_id or not step.step_id.strip():
                raise InvalidPlanError(f"Step at index {idx} has an empty step_id.")
            if step.step_id in step_ids:
                raise InvalidPlanError(f"Duplicate step_id '{step.step_id}' found in plan.")
            step_ids.add(step.step_id)

            if not step.description or not step.description.strip():
                raise InvalidPlanError(f"Step '{step.step_id}' has an empty description.")

            if not step.capability or not step.capability.strip():
                raise InvalidPlanError(f"Step '{step.step_id}' has an empty capability.")

            # Validate agent existence
            if not self.agent_registry.exists(step.agent_id):
                raise UnknownAgentError(
                    f"Step '{step.step_id}' references unknown agent '{step.agent_id}'."
                )

            agent = self.agent_registry.get(step.agent_id)
            if not agent.enabled:
                raise InvalidPlanError(f"Agent '{step.agent_id}' is disabled.")

            # Validate agent possesses capability
            if step.capability not in agent.capabilities:
                raise InvalidPlanError(
                    f"Agent '{step.agent_id}' does not advertise required capability '{step.capability}'. "
                    f"Available: {agent.capabilities}"
                )

            # Validate tool existence
            for tool_id in step.required_tools:
                if not self.tool_registry.exists(tool_id):
                    raise UnknownToolError(
                        f"Step '{step.step_id}' references unknown tool '{tool_id}'."
                    )
                tool = self.tool_registry.get(tool_id)
                if not tool.enabled:
                    raise InvalidPlanError(f"Tool '{tool_id}' is disabled.")

        # Validate dependencies exist
        for step in steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    raise InvalidPlanError(
                        f"Step '{step.step_id}' depends on non-existent step '{dep}'."
                    )
                if dep == step.step_id:
                    raise InvalidPlanError(
                        f"Step '{step.step_id}' cannot depend on itself."
                    )

        # Validate DAG acyclicity
        self._check_cycles(steps)

    def _check_cycles(self, steps: List[PlanStep]) -> None:
        """Detect circular dependencies using DFS graph coloring."""
        adj: Dict[str, List[str]] = {s.step_id: s.dependencies for s in steps}
        visited: Dict[str, int] = {s.step_id: 0 for s in steps}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(node: str) -> None:
            visited[node] = 1
            for neighbor in adj.get(node, []):
                if visited[neighbor] == 1:
                    raise InvalidPlanError(f"Circular dependency detected involving step '{neighbor}'.")
                if visited[neighbor] == 0:
                    dfs(neighbor)
            visited[node] = 2

        for step in steps:
            if visited[step.step_id] == 0:
                dfs(step.step_id)


def create_default_plan_for_capabilities(
    user_request: str,
    capabilities: List[str],
    selected_agents: Dict[str, str],
    agent_registry: AgentRegistry,
    tool_registry: ToolRegistry,
) -> List[PlanStep]:
    """Deterministically assemble an initial plan mapping capabilities to steps."""
    steps: List[PlanStep] = []
    prev_step_id: Optional[str] = None

    for idx, cap in enumerate(capabilities, start=1):
        agent_id = selected_agents.get(cap)
        if not agent_id:
            candidates = agent_registry.find_by_capability(cap)
            if candidates:
                agent_id = candidates[0].agent_id
            else:
                agent_id = "main_agent"

        agent = agent_registry.get(agent_id)
        tools = [t for t in (agent.allowed_tools if agent else []) if tool_registry.exists(t)]

        step_id = f"step_{idx}"
        deps = [prev_step_id] if prev_step_id else []

        step = PlanStep(
            step_id=step_id,
            description=f"Execute {cap} task",
            capability=cap,
            agent_id=agent_id,
            required_tools=tools,
            dependencies=deps,
            expected_output=f"result_of_{cap}",
            verification_required=True,
        )
        steps.append(step)
        prev_step_id = step_id

    return steps

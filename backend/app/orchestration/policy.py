"""Policy checkpoint integration for pre-execution risk and approval evaluation."""

from typing import List, Optional, Dict, Any, Union
from backend.app.tools.registry import ToolRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.security.policy_engine import (
    PolicyDecision,
    PolicyOutcome,
    PolicyEngine,
)
from backend.app.security.risk import RiskAssessment


class PolicyEvaluator:
    """Evaluates plan steps against tool risks and approval requirements using PolicyEngine."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        agent_registry: Optional[AgentRegistry] = None,
        policy_config_path: Optional[str] = None,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.agent_registry = agent_registry or AgentRegistry()
        self.engine = PolicyEngine(
            tool_registry=self.tool_registry,
            agent_registry=self.agent_registry,
            policy_config_path=policy_config_path,
        )

    def evaluate_step(self, step: Any) -> PolicyDecision:
        """Evaluate a single plan step."""
        return self.engine.evaluate_step(step)

    def evaluate_plan(
        self,
        steps: List[Any],
        task_id: str = "",
        plan_id: str = "",
        data_sensitivity: Any = "INTERNAL",
    ) -> PolicyDecision:
        """Evaluate an entire plan before execution."""
        decision, _ = self.engine.evaluate_plan(
            plan_steps=steps,
            task_id=task_id,
            plan_id=plan_id,
            data_sensitivity=data_sensitivity,
        )
        return decision

    def evaluate_plan_with_assessment(
        self,
        steps: List[Any],
        task_id: str = "",
        plan_id: str = "",
        data_sensitivity: Any = "INTERNAL",
    ) -> tuple[PolicyDecision, RiskAssessment]:
        """Evaluate plan returning both decision and risk assessment."""
        return self.engine.evaluate_plan(
            plan_steps=steps,
            task_id=task_id,
            plan_id=plan_id,
            data_sensitivity=data_sensitivity,
        )

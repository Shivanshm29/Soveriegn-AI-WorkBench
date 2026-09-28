"""State interpretation and outcome assessment for plan step observations."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, Literal, List
from pydantic import BaseModel, Field

from backend.app.orchestration.execution import AgentExecutionResult
from backend.app.orchestration.planner import PlanStep


class StepObservation(BaseModel):
    """Interpreted outcome of a plan step execution."""

    step_id: str
    agent_id: str
    outcome: Literal["SUCCESS", "RECOVERABLE_FAILURE", "FATAL_FAILURE"]
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(mode="json")


class ObservationEvaluator:
    """Evaluates agent execution results to determine observation state and next steps."""

    @staticmethod
    def evaluate(
        step: PlanStep,
        result: AgentExecutionResult,
    ) -> StepObservation:
        """Interpret execution result into a structured StepObservation."""
        if result.status == "SUCCESS":
            evidence = []
            if "evidence" in result.output and isinstance(result.output["evidence"], list):
                evidence = result.output["evidence"]
            return StepObservation(
                step_id=step.step_id,
                agent_id=step.agent_id,
                outcome="SUCCESS",
                output=result.output,
                evidence_references=evidence,
            )

        if result.status == "NOT_IMPLEMENTED":
            return StepObservation(
                step_id=step.step_id,
                agent_id=step.agent_id,
                outcome="FATAL_FAILURE",
                error=result.error or f"Capability '{step.capability}' not implemented for agent '{step.agent_id}'.",
            )

        # Standard failure: determine if recoverable or fatal
        error_msg = result.error or "Unknown step execution failure"
        fatal_keywords = ["unregistered", "syntaxerror", "security_violation", "blocked"]
        is_fatal = any(kw in error_msg.lower() for kw in fatal_keywords)

        return StepObservation(
            step_id=step.step_id,
            agent_id=step.agent_id,
            outcome="FATAL_FAILURE" if is_fatal else "RECOVERABLE_FAILURE",
            error=error_msg,
        )

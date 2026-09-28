"""Test G: Observation Node and State Evaluation."""

import pytest
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.execution import AgentExecutionResult
from backend.app.orchestration.observation import ObservationEvaluator, StepObservation


def test_observation_evaluates_success():
    """Verify success outcome creates successful StepObservation."""
    step = PlanStep(
        step_id="s1",
        description="Extract tables",
        capability="data_analysis",
        agent_id="data_agent",
    )
    result = AgentExecutionResult(
        status="SUCCESS",
        agent_id="data_agent",
        output={"rows": 100, "evidence": ["table_1"]},
    )
    obs = ObservationEvaluator.evaluate(step, result)
    assert obs.outcome == "SUCCESS"
    assert obs.output["rows"] == 100
    assert obs.evidence_references == ["table_1"]


def test_observation_evaluates_recoverable_failure():
    """Verify transient error is evaluated as RECOVERABLE_FAILURE."""
    step = PlanStep(
        step_id="s2",
        description="Search knowledge",
        capability="knowledge_search",
        agent_id="knowledge_agent",
    )
    result = AgentExecutionResult(
        status="FAILED",
        agent_id="knowledge_agent",
        error="Temporary connection timeout to local index",
    )
    obs = ObservationEvaluator.evaluate(step, result)
    assert obs.outcome == "RECOVERABLE_FAILURE"
    assert "timeout" in obs.error.lower()


def test_observation_evaluates_fatal_failure():
    """Verify fatal unrecoverable errors are evaluated as FATAL_FAILURE."""
    step = PlanStep(
        step_id="s3",
        description="Run query",
        capability="reasoning",
        agent_id="reasoning_agent",
    )
    result = AgentExecutionResult(
        status="FAILED",
        agent_id="reasoning_agent",
        error="Security_violation: Attempted access outside allowed boundary",
    )
    obs = ObservationEvaluator.evaluate(step, result)
    assert obs.outcome == "FATAL_FAILURE"

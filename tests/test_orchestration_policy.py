"""Test E: Policy Checkpoint Integration."""

import pytest
from backend.app.tools.registry import ToolRegistry, ToolContract
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.policy import PolicyEvaluator, PolicyDecision


def test_policy_allows_safe_step():
    """Verify safe steps evaluate to allowed."""
    evaluator = PolicyEvaluator(ToolRegistry())
    step = PlanStep(
        step_id="s1",
        description="Read document",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )
    decision = evaluator.evaluate_step(step)
    assert decision.status == "allowed"
    assert not decision.requires_approval


def test_policy_detects_requires_approval_tool():
    """Verify high-risk tools requiring approval trigger requires_approval status."""
    evaluator = PolicyEvaluator(ToolRegistry())
    step = PlanStep(
        step_id="s2",
        description="Execute untrusted sandbox code",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    decision = evaluator.evaluate_step(step)
    assert decision.status == "requires_approval"
    assert decision.requires_approval is True
    assert "sandbox_execute" in decision.flagged_tools


def test_policy_evaluates_entire_plan():
    """Verify plan containing approval-required tools flags the plan."""
    evaluator = PolicyEvaluator(ToolRegistry())
    steps = [
        PlanStep(
            step_id="s1",
            description="Read file",
            capability="document_extraction",
            agent_id="document_agent",
            required_tools=["file_read"],
        ),
        PlanStep(
            step_id="s2",
            description="Run sandbox",
            capability="code_execution",
            agent_id="coding_agent",
            required_tools=["sandbox_execute"],
        ),
    ]
    plan_decision = evaluator.evaluate_plan(steps)
    assert plan_decision.status == "requires_approval"
    assert "sandbox_execute" in plan_decision.flagged_tools

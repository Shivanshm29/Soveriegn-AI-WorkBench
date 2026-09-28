"""Test F: Agent Execution Mechanism and A2A Messaging."""

import pytest
from backend.app.agents.registry import AgentRegistry, UnknownAgentError
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.execution import AgentExecutor, AgentExecutionResult


@pytest.fixture
def executor():
    return AgentExecutor(
        agent_registry=AgentRegistry(),
        tool_registry=ToolRegistry(),
    )


def test_truthful_execution_returns_not_implemented(executor):
    """Verify that unimplemeted capabilities return NOT_IMPLEMENTED truthfully without faking success."""
    step = PlanStep(
        step_id="step_ocr",
        description="Extract OCR from scanned document",
        capability="scanned_page_analysis",
        agent_id="vision_agent",
    )
    result = executor.execute("vision_agent", step, {"user_request": "OCR this document"})

    assert isinstance(result, AgentExecutionResult)
    assert result.status == "NOT_IMPLEMENTED"
    assert "not implemented" in result.error.lower()
    # Verify A2A messages
    assert result.delegation_message is not None
    assert result.delegation_message.type == "TASK_DELEGATION"
    assert result.result_message is not None
    assert result.result_message.type == "TASK_RESULT"


def test_execution_with_registered_handler(executor):
    """Verify execution succeeds when a specialist handler or test double is registered."""
    executor.register_handler(
        "coding_agent",
        lambda step, ctx: {"code": "def hello(): return 'world'", "status": "generated"},
    )
    step = PlanStep(
        step_id="step_code",
        description="Generate code",
        capability="code_generation",
        agent_id="coding_agent",
    )
    result = executor.execute("coding_agent", step, {"user_request": "Write hello world"})

    assert result.status == "SUCCESS"
    assert result.output["code"] == "def hello(): return 'world'"
    assert result.delegation_message.type == "TASK_DELEGATION"
    assert result.result_message.type == "TASK_RESULT"
    assert result.result_message.status == "COMPLETED"


def test_execution_with_unknown_agent_fails(executor):
    """Verify execution with unregistered agent raises UnknownAgentError."""
    step = PlanStep(
        step_id="s1",
        description="Action",
        capability="reasoning",
        agent_id="non_existent_agent",
    )
    with pytest.raises(UnknownAgentError):
        executor.execute("non_existent_agent", step, {})


def test_execution_handler_failure_handled_cleanly(executor):
    """Verify exceptions in agent handlers return structured FAILED results."""
    def failing_handler(step, ctx):
        raise RuntimeError("Disk quota exceeded during processing")

    executor.register_handler("data_agent", failing_handler)
    step = PlanStep(
        step_id="s_fail",
        description="Calculate metrics",
        capability="calculation",
        agent_id="data_agent",
    )
    result = executor.execute("data_agent", step, {})
    assert result.status == "FAILED"
    assert "Disk quota exceeded" in result.error
    assert result.result_message.type == "ERROR"

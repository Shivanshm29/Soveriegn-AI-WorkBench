"""Tests for Agent-to-Agent (A2A) structured communication and validation."""

import pytest
from backend.app.schemas.agents import A2AMessage
from backend.app.agents.registry import AgentRegistry, UnknownAgentError
from backend.app.agents.a2a import (
    A2AMessageValidator,
    InvalidA2AMessageError,
    create_a2a_request,
    create_a2a_response,
    create_a2a_error,
)


def test_create_a2a_request_message():
    """Verify factory creation of A2A REQUEST message."""
    msg = create_a2a_request(
        task_id="task-99",
        sender="main_agent",
        receiver="document_agent",
        payload={"document_path": "report.pdf"},
        requested_capabilities=["document_extraction"],
    )
    assert msg.type == "REQUEST"
    assert msg.sender == "main_agent"
    assert msg.receiver == "document_agent"
    assert msg.payload["document_path"] == "report.pdf"
    assert msg.status == "PENDING"
    assert "document_extraction" in msg.requested_capabilities


def test_create_a2a_response_message():
    """Verify factory creation of A2A RESPONSE message."""
    msg = create_a2a_response(
        task_id="task-99",
        sender="document_agent",
        receiver="main_agent",
        payload={"text": "Extracted text content"},
    )
    assert msg.type == "RESPONSE"
    assert msg.sender == "document_agent"
    assert msg.receiver == "main_agent"
    assert msg.status == "COMPLETED"


def test_create_a2a_error_message():
    """Verify factory creation of A2A ERROR message."""
    msg = create_a2a_error(
        task_id="task-99",
        sender="document_agent",
        receiver="main_agent",
        error_message="File corrupt or unreadable",
    )
    assert msg.type == "ERROR"
    assert msg.payload["error"] == "File corrupt or unreadable"
    assert msg.status == "FAILED"


def test_a2a_validation_success():
    """Verify valid A2A message validates against AgentRegistry."""
    registry = AgentRegistry()
    msg = create_a2a_request(
        task_id="task-100",
        sender="main_agent",
        receiver="coding_agent",
        payload={"code_spec": "def test(): pass"},
        requested_capabilities=["code_generation"],
    )
    # Should not raise
    A2AMessageValidator.validate(msg, agent_registry=registry)


def test_a2a_self_messaging_rejected():
    """Verify agent cannot send message to itself."""
    registry = AgentRegistry()
    msg = create_a2a_request(
        task_id="task-100",
        sender="main_agent",
        receiver="main_agent",
    )
    with pytest.raises(InvalidA2AMessageError) as exc_info:
        A2AMessageValidator.validate(msg, agent_registry=registry)
    assert "Self-messaging not permitted" in str(exc_info.value)


def test_a2a_unknown_agent_rejected():
    """Verify message with unregistered agent is rejected."""
    registry = AgentRegistry()
    msg = create_a2a_request(
        task_id="task-100",
        sender="main_agent",
        receiver="cloud_gpt4_agent",
    )
    with pytest.raises(UnknownAgentError):
        A2AMessageValidator.validate(msg, agent_registry=registry)


def test_a2a_capability_delegation_rule_enforced():
    """Verify receiver must declare requested capabilities per AGENTS.md."""
    registry = AgentRegistry()

    # data_agent does NOT declare visual_reasoning
    invalid_delegation = create_a2a_request(
        task_id="task-100",
        sender="main_agent",
        receiver="data_agent",
        requested_capabilities=["visual_reasoning"],
    )
    with pytest.raises(InvalidA2AMessageError) as exc_info:
        A2AMessageValidator.validate(invalid_delegation, agent_registry=registry)
    assert "lacks required capabilities" in str(exc_info.value)

    # vision_agent DOES declare visual_reasoning
    valid_delegation = create_a2a_request(
        task_id="task-100",
        sender="main_agent",
        receiver="vision_agent",
        requested_capabilities=["visual_reasoning"],
    )
    # Should pass without error
    A2AMessageValidator.validate(valid_delegation, agent_registry=registry)

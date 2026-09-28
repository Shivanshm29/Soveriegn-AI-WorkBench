"""Agent-to-Agent (A2A) structured communication and validation."""

import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from backend.app.schemas.agents import A2AMessage
from backend.app.agents.registry import AgentRegistry, UnknownAgentError


class A2AMessageType(str, Enum):
    """Supported A2A message types."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    DELEGATION = "DELEGATION"
    NOTIFICATION = "NOTIFICATION"
    TASK_DELEGATION = "TASK_DELEGATION"
    TASK_RESULT = "TASK_RESULT"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    INFORMATION_RESPONSE = "INFORMATION_RESPONSE"
    TOOL_REQUEST = "TOOL_REQUEST"
    TOOL_RESULT = "TOOL_RESULT"
    ERROR = "ERROR"
    STATUS_UPDATE = "STATUS_UPDATE"


class InvalidA2AMessageError(Exception):
    """Raised when an A2A message fails structural or semantic validation."""
    pass


class A2AMessageValidator:
    """Validates structured A2A messages against contracts and registries."""

    @staticmethod
    def validate(message: A2AMessage, agent_registry: Optional[AgentRegistry] = None) -> None:
        """Validate format, agent existence, and capability compliance."""
        if not message.message_id or not message.message_id.strip():
            raise InvalidA2AMessageError("Message ID must not be empty.")

        if not message.task_id or not message.task_id.strip():
            raise InvalidA2AMessageError("Task ID must not be empty.")

        if not message.sender or not message.sender.strip():
            raise InvalidA2AMessageError("Sender must not be empty.")

        if not message.receiver or not message.receiver.strip():
            raise InvalidA2AMessageError("Receiver must not be empty.")

        if message.sender == message.receiver:
            raise InvalidA2AMessageError(
                f"Self-messaging not permitted: sender and receiver are both '{message.sender}'."
            )

        if agent_registry is not None:
            # Verify sender exists and is enabled
            if not agent_registry.exists(message.sender):
                raise UnknownAgentError(f"Unknown sender agent: '{message.sender}'.")
            sender_agent = agent_registry.get(message.sender)
            if sender_agent and not sender_agent.enabled:
                raise InvalidA2AMessageError(f"Sender agent '{message.sender}' is disabled.")

            # Verify receiver exists and is enabled
            if not agent_registry.exists(message.receiver):
                raise UnknownAgentError(f"Unknown receiver agent: '{message.receiver}'.")
            receiver_agent = agent_registry.get(message.receiver)
            if receiver_agent and not receiver_agent.enabled:
                raise InvalidA2AMessageError(f"Receiver agent '{message.receiver}' is disabled.")

            # Capability verification for delegations / capability requests
            if message.requested_capabilities and receiver_agent:
                missing = [
                    cap for cap in message.requested_capabilities
                    if cap not in receiver_agent.capabilities
                ]
                if missing:
                    raise InvalidA2AMessageError(
                        f"Receiver agent '{message.receiver}' lacks required capabilities: {missing}. "
                        f"Available: {receiver_agent.capabilities}"
                    )


def create_a2a_request(
    task_id: str,
    sender: str,
    receiver: str,
    payload: Optional[Dict[str, Any]] = None,
    requested_capabilities: Optional[List[str]] = None,
    correlation_id: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> A2AMessage:
    """Helper to construct a structured A2A REQUEST message."""
    return A2AMessage(
        message_id=str(uuid.uuid4()),
        task_id=task_id,
        sender=sender,
        receiver=receiver,
        type="REQUEST",
        correlation_id=correlation_id,
        payload=payload or {},
        provenance=provenance or {},
        requested_capabilities=requested_capabilities or [],
        status="PENDING",
    )


def create_a2a_response(
    task_id: str,
    sender: str,
    receiver: str,
    payload: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> A2AMessage:
    """Helper to construct a structured A2A RESPONSE message."""
    return A2AMessage(
        message_id=str(uuid.uuid4()),
        task_id=task_id,
        sender=sender,
        receiver=receiver,
        type="RESPONSE",
        correlation_id=correlation_id,
        payload=payload or {},
        provenance=provenance or {},
        status="COMPLETED",
    )


def create_a2a_error(
    task_id: str,
    sender: str,
    receiver: str,
    error_message: str,
    correlation_id: Optional[str] = None,
) -> A2AMessage:
    """Helper to construct a structured A2A ERROR message."""
    return A2AMessage(
        message_id=str(uuid.uuid4()),
        task_id=task_id,
        sender=sender,
        receiver=receiver,
        type="ERROR",
        correlation_id=correlation_id,
        payload={"error": error_message},
        status="FAILED",
    )

"""Agent contract and communication schemas."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class AgentContract(BaseModel):
    """Specification of an agent per AGENTS.md contract."""

    agent_id: str
    description: str
    name: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    accepted_inputs: List[str] = Field(default_factory=list)
    accepted_input_modalities: List[str] = Field(default_factory=lambda: ["text"])
    produced_outputs: List[str] = Field(default_factory=list)
    output_types: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    preferred_model_capabilities: List[str] = Field(default_factory=list)
    risk_class: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    max_retries: int = 2
    version: str = "1.0.0"
    enabled: bool = True


class A2AMessage(BaseModel):
    """Structured Agent-to-Agent message per AGENTS.md."""

    message_id: str
    task_id: str
    sender: str
    receiver: str
    type: Literal[
        "REQUEST",
        "RESPONSE",
        "DELEGATION",
        "NOTIFICATION",
        "TASK_DELEGATION",
        "TASK_RESULT",
        "INFORMATION_REQUEST",
        "INFORMATION_RESPONSE",
        "TOOL_REQUEST",
        "TOOL_RESULT",
        "ERROR",
        "STATUS_UPDATE",
    ]
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    requested_capabilities: List[str] = Field(default_factory=list)
    status: str = "PENDING"

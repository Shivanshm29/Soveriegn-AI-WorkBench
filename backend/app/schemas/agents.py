"""Agent contract and communication schemas."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class AgentContract(BaseModel):
    """Specification of an agent per AGENTS.md contract."""

    agent_id: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    accepted_inputs: List[str] = Field(default_factory=list)
    produced_outputs: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    risk_class: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    max_retries: int = 2


class A2AMessage(BaseModel):
    """Structured Agent-to-Agent message per AGENTS.md."""

    message_id: str
    task_id: str
    sender: str
    receiver: str
    type: Literal["REQUEST", "RESPONSE", "DELEGATION", "NOTIFICATION"]
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

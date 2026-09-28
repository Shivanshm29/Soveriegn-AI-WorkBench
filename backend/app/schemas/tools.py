"""Tool contract schemas."""

from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field


class ToolContract(BaseModel):
    """Specification of a tool registered in the workbench."""

    tool_id: str
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    requires_approval: bool = False

"""Tool contract schemas."""

from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field


class ToolContract(BaseModel):
    """Specification of a tool registered in the workbench."""

    tool_id: str
    name: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    requires_approval: bool = False
    enabled: bool = True


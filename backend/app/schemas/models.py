"""Model profile and definition schemas."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class ModelDefinition(BaseModel):
    """Definition of a single model candidate within a profile."""

    id: str
    model_name: str
    capabilities: List[str] = Field(default_factory=list)
    input_modalities: List[str] = Field(default_factory=lambda: ["text"])
    output_modalities: List[str] = Field(default_factory=lambda: ["text"])
    preferred_runtime: str = "vllm"
    enabled: bool = True
    family: Optional[str] = None
    profile: Optional[str] = None
    context_length: Optional[int] = 16384
    tool_calling: bool = True
    structured_output: bool = True
    quantization: Optional[str] = None
    min_vram_gb: Optional[float] = None


class ModelProfileConfig(BaseModel):
    """Complete specification of a model profile loaded from YAML."""

    profile: Literal["small", "high"]
    description: str
    models: Dict[str, ModelDefinition]


class ModelSelection(BaseModel):
    """The result of model resolution."""

    selected_model_id: str
    selected_model_name: str
    active_profile: str
    capabilities: List[str] = Field(default_factory=list)
    reason: List[str] = Field(default_factory=list)
    hardware_snapshot: Optional[Dict[str, Any]] = None

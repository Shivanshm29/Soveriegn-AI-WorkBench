"""Model profile and definition schemas."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "model_id" in data and "id" not in data:
                data["id"] = data["model_id"]
            if "name" in data and "model_name" not in data:
                data["model_name"] = data["name"]
            if "context_window" in data and "context_length" not in data:
                data["context_length"] = data["context_window"]
        return data

    @property
    def model_id(self) -> str:
        return self.id

    @property
    def name(self) -> str:
        return self.model_name

    @property
    def context_window(self) -> int:
        return self.context_length or 16384



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

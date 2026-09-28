"""Health check abstractions and statuses for model runtime."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health statuses for local model runtime."""

    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MISCONFIGURED = "misconfigured"
    MODEL_NOT_FOUND = "model_not_found"
    UNKNOWN_ERROR = "unknown_error"


class RuntimeHealth(BaseModel):
    """Structured health check result for local runtime."""

    status: HealthStatus
    runtime: str
    base_url: str
    models: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

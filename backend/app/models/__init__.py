"""Models module for Sovereign Workbench."""

from backend.app.models.runtime import ModelRuntime
from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.registry import ModelRegistry
from backend.app.models.health import HealthStatus, RuntimeHealth
from backend.app.models.hardware import HardwareSnapshot, probe_hardware
from backend.app.models.lifecycle import ModelLifecycleManager, SimpleModelLifecycleManager
from backend.app.models.schemas import (
    ModelRequest,
    ModelResponse,
    ChatMessage,
    ContentPart,
    ToolCall,
    FunctionCall,
    UsageMetadata,
)
from backend.app.models.errors import (
    ModelRuntimeError,
    ModelUnavailableError,
    ModelTimeoutError,
    ModelNotFoundError,
    ModelConfigurationError,
    ModelResponseError,
    ModelCapabilityError,
)

__all__ = [
    "ModelRuntime",
    "LocalOpenAIRuntime",
    "create_model_runtime",
    "ModelRegistry",
    "HealthStatus",
    "RuntimeHealth",
    "HardwareSnapshot",
    "probe_hardware",
    "ModelLifecycleManager",
    "SimpleModelLifecycleManager",
    "ModelRequest",
    "ModelResponse",
    "ChatMessage",
    "ContentPart",
    "ToolCall",
    "FunctionCall",
    "UsageMetadata",
    "ModelRuntimeError",
    "ModelUnavailableError",
    "ModelTimeoutError",
    "ModelNotFoundError",
    "ModelConfigurationError",
    "ModelResponseError",
    "ModelCapabilityError",
]

"""Factory for instantiating model runtimes."""

from typing import Optional
from backend.app.config.settings import Settings, get_settings
from backend.app.models.runtime import ModelRuntime
from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.errors import ModelConfigurationError


def create_model_runtime(settings: Optional[Settings] = None) -> ModelRuntime:
    """Create and configure a ModelRuntime based on application settings."""
    cfg = settings or get_settings()

    runtime_type = cfg.MODEL_RUNTIME.lower()
    if runtime_type in ("vllm", "openai_compatible", "local_openai", "llamacpp"):
        return LocalOpenAIRuntime(
            base_url=cfg.MODEL_BASE_URL,
            api_key=cfg.MODEL_API_KEY,
            timeout=cfg.MODEL_REQUEST_TIMEOUT_SECONDS,
            health_timeout=cfg.MODEL_HEALTH_TIMEOUT_SECONDS,
            sovereign_mode=cfg.SOVEREIGN_MODE,
            runtime_name=runtime_type,
        )
    else:
        raise ModelConfigurationError(
            f"Unsupported MODEL_RUNTIME '{cfg.MODEL_RUNTIME}'. "
            f"Supported options: ['vllm', 'local_openai', 'llamacpp']"
        )

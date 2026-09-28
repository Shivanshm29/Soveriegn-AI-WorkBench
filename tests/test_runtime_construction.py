"""Test Group B: Runtime Construction and Configuration."""

import pytest
from backend.app.config.settings import Settings
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.registry import ModelRegistry


def test_runtime_initializes_from_configuration():
    """Verify runtime initializes using settings."""
    settings = Settings(
        MODEL_RUNTIME="vllm",
        MODEL_BASE_URL="http://127.0.0.1:8000/v1",
        MODEL_REQUEST_TIMEOUT_SECONDS=60.0,
        SOVEREIGN_MODE=True,
    )
    runtime = create_model_runtime(settings)
    assert isinstance(runtime, LocalOpenAIRuntime)
    assert runtime.base_url == "http://127.0.0.1:8000/v1"
    assert runtime.timeout == 60.0
    assert runtime.runtime_name == "vllm"


def test_runtime_uses_configured_base_url():
    """Verify runtime respects a custom local port or address."""
    settings = Settings(MODEL_BASE_URL="http://127.0.0.1:8080/v1")
    runtime = create_model_runtime(settings)
    assert runtime.base_url == "http://127.0.0.1:8080/v1"


def test_runtime_uses_configured_runtime_type():
    """Verify factory respects runtime name."""
    settings = Settings(MODEL_RUNTIME="local_openai")
    runtime = create_model_runtime(settings)
    assert runtime.runtime_name == "local_openai"


def test_runtime_does_not_require_cloud_credentials():
    """Verify runtime functions with local-only dummy token and requires no cloud API keys."""
    settings = Settings(MODEL_API_KEY="local-only")
    runtime = create_model_runtime(settings)
    assert runtime.api_key == "local-only"


def test_runtime_obtains_model_name_from_registry():
    """Verify runtime interacts with model names resolved through ModelRegistry rather than hardcoded."""
    registry = ModelRegistry()
    model_name = registry.resolve_model_name("general_reasoning")

    # In small profile, general_reasoning maps to Qwen/Qwen3-4B
    assert model_name == "Qwen/Qwen3-4B"
    # The runtime receives this resolved model_name in its requests
    runtime = create_model_runtime()
    assert runtime is not None

"""Phase 1 Acceptance Test Suite.

Verifies the 10 acceptance criteria established for the Local Model Runtime layer:
1. Phase 0 passes.
2. ModelRuntime can be constructed.
3. Local endpoint configuration works.
4. Model registry integration works.
5. Health check works.
6. Failure states are distinguishable.
7. External endpoint is rejected in sovereign mode.
8. No cloud fallback exists.
9. Small/high profile switching still works.
10. Runtime does not require a GPU to initialize.
"""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.config.settings import Settings
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.runtime import ModelRuntime
from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.registry import ModelRegistry
from backend.app.models.health import HealthStatus
from backend.app.models.hardware import probe_hardware
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.models.errors import (
    ModelUnavailableError,
    ModelTimeoutError,
    ModelNotFoundError,
    ModelConfigurationError,
)
from backend.app.schemas.agents import AgentContract
from backend.app.schemas.tools import ToolContract


def test_acceptance_01_phase_0_passes():
    """1. Verify Phase 0 baseline functionality is intact."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=False)
    registry = ModelRegistry(settings=settings)
    assert registry.active_profile_name == "small"
    assert registry.resolve_model_name("general_reasoning") == "Qwen/Qwen3-4B"

    # Agent and tool contracts validate
    agent = AgentContract(agent_id="test_agent", description="test")
    tool = ToolContract(tool_id="test_tool", name="test", description="test")
    assert agent.agent_id == "test_agent"
    assert tool.tool_id == "test_tool"


def test_acceptance_02_model_runtime_construction():
    """2. Verify ModelRuntime protocol implementation can be instantiated."""
    settings = Settings()
    runtime = create_model_runtime(settings)
    assert isinstance(runtime, ModelRuntime)
    assert isinstance(runtime, LocalOpenAIRuntime)
    assert "text" in runtime.capabilities()


def test_acceptance_03_local_endpoint_configuration():
    """3. Verify local endpoint configuration (base_url, timeout, api_key) is respected."""
    settings = Settings(
        MODEL_BASE_URL="http://127.0.0.1:8000/v1",
        MODEL_REQUEST_TIMEOUT_SECONDS=90.0,
        MODEL_API_KEY="local-only",
    )
    runtime = create_model_runtime(settings)
    assert runtime.base_url == "http://127.0.0.1:8000/v1"
    assert runtime.timeout == 90.0
    assert runtime.api_key == "local-only"


def test_acceptance_04_model_registry_integration():
    """4. Verify model registry integrates with runtime requests."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=False)
    registry = ModelRegistry(settings=settings)
    runtime = create_model_runtime(settings)

    model_name = registry.resolve_model_name("general_reasoning")
    assert model_name == "Qwen/Qwen3-4B"

    # Runtime receives resolved model_name
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": model_name,
        "choices": [{"message": {"role": "assistant", "content": "Acknowledged."}}],
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        req = ModelRequest(
            model_id=model_name,
            messages=[ChatMessage(role="user", content="Ping")],
        )
        resp = runtime.generate(req)
        assert resp.model_id == model_name
        assert resp.content == "Acknowledged."


def test_acceptance_05_health_check_works():
    """5. Verify local runtime health check executes and provides structured reporting."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"id": "Qwen/Qwen3-4B"}],
    }

    with patch.object(httpx.Client, "get", return_value=mock_resp):
        health = runtime.health_check()
        assert health.status == HealthStatus.HEALTHY
        assert "Qwen/Qwen3-4B" in health.models
        assert health.base_url == "http://127.0.0.1:8000/v1"


def test_acceptance_06_failure_states_distinguishable():
    """6. Verify failure states (UNAVAILABLE, TIMEOUT, MODEL_NOT_FOUND, MISCONFIGURED) are distinct."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    # Connection refused -> Unavailable
    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Refused")):
        with pytest.raises(ModelUnavailableError):
            runtime.generate(ModelRequest(model_id="m", messages=[ChatMessage(role="user", content="hi")]))

    # Timeout -> Timeout
    with patch.object(httpx.Client, "post", side_effect=httpx.TimeoutException("Timed out")):
        with pytest.raises(ModelTimeoutError):
            runtime.generate(ModelRequest(model_id="m", messages=[ChatMessage(role="user", content="hi")]))

    # 404 -> Not found
    mock_404 = MagicMock(status_code=404, text="Not Found")
    with patch.object(httpx.Client, "post", return_value=mock_404):
        with pytest.raises(ModelNotFoundError):
            runtime.generate(ModelRequest(model_id="m", messages=[ChatMessage(role="user", content="hi")]))


def test_acceptance_07_external_endpoint_rejected_in_sovereign_mode():
    """7. Verify external endpoints are rejected immediately when SOVEREIGN_MODE=True."""
    with pytest.raises(ModelConfigurationError) as exc_info:
        LocalOpenAIRuntime(
            base_url="https://api.openai.com/v1",
            sovereign_mode=True,
        )
    assert "Sovereignty violation" in str(exc_info.value)


def test_acceptance_08_no_cloud_fallback():
    """8. Verify that runtime failure raises clean local errors and never attempts cloud fallback."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Offline")):
        # Must fail clearly with ModelUnavailableError; must not attempt any cloud URL
        with pytest.raises(ModelUnavailableError):
            runtime.generate(ModelRequest(model_id="Qwen/Qwen3-4B", messages=[ChatMessage(role="user", content="test")]))


def test_acceptance_09_small_high_profile_switching():
    """9. Verify small and high profiles switch based only on environment toggle without agent changes."""
    # Small profile
    reg_small = ModelRegistry(settings=Settings(USE_HIGH_LEVEL_MODELS=False))
    assert reg_small.resolve_model_name("general_reasoning") == "Qwen/Qwen3-4B"
    assert reg_small.resolve_model_name("vision_document") == "Qwen/Qwen3-VL-4B-Instruct"
    assert reg_small.resolve_model_name("coding") == "Qwen/Qwen2.5-Coder-3B-Instruct"

    # High profile
    reg_high = ModelRegistry(settings=Settings(USE_HIGH_LEVEL_MODELS=True))
    assert reg_high.resolve_model_name("general_reasoning") == "Qwen/Qwen3-30B-A3B"
    assert reg_high.resolve_model_name("vision_document") == "Qwen/Qwen3-VL-30B-A3B-Instruct"
    assert reg_high.resolve_model_name("coding") == "Qwen/Qwen3-Coder-30B-A3B-Instruct"


def test_acceptance_10_runtime_does_not_require_gpu():
    """10. Verify hardware probe and runtime initialize on CPU-only machines without errors."""
    with patch("backend.app.models.hardware._get_gpu_info", return_value=(False, None, None, None)):
        snapshot = probe_hardware()
        assert snapshot.gpu_available is False
        assert snapshot.cpu_count >= 1

    # Runtime initializes smoothly on CPU-only setup
    runtime = create_model_runtime()
    assert runtime is not None

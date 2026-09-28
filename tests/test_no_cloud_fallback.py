"""Phase 2 Tests: No Cloud Model Fallback (Test I)."""

from unittest.mock import patch
import httpx
import pytest

from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.models.errors import ModelUnavailableError
from backend.app.config.settings import Settings


def test_local_failure_fails_closed_without_cloud_fallback():
    """Test I: Verify local server failure immediately raises local error with zero cloud attempts."""
    settings = Settings(
        MODEL_BASE_URL="http://127.0.0.1:8000/v1",
        ALLOW_CLOUD_MODELS=False,
        SOVEREIGN_MODE=True,
    )
    runtime = create_model_runtime(settings)

    # Simulate local connection refused
    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Offline")):
        with pytest.raises(ModelUnavailableError) as exc_info:
            runtime.generate(
                ModelRequest(
                    model_id="Qwen/Qwen3-4B",
                    messages=[ChatMessage(role="user", content="Classify document")],
                )
            )
        assert "unreachable" in str(exc_info.value) or "refused" in str(exc_info.value).lower()

    # Verify no cloud model fallback is registered or configured
    assert settings.ALLOW_CLOUD_MODELS is False

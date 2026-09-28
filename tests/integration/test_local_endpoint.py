"""Test Group C: Real local endpoint integration test."""

import httpx
import pytest

from backend.app.config.settings import Settings
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.models.health import HealthStatus


def test_real_local_endpoint_if_available():
    """Execute real inference against a live local server if present, or cleanly skip.

    Never fakes a successful response when no local server is active.
    """
    settings = Settings()
    runtime = create_model_runtime(settings)

    # Probe live endpoint
    try:
        health = runtime.health_check()
    except Exception as e:
        pytest.skip(f"Local model server at {settings.MODEL_BASE_URL} unavailable: {e}")

    if health.status != HealthStatus.HEALTHY or not health.models:
        pytest.skip(
            f"Local model server at {settings.MODEL_BASE_URL} is not ready or has no loaded models "
            f"(status={health.status.value}, error={health.error})."
        )

    # If active, pick the first available model
    available_model = health.models[0]

    req = ModelRequest(
        model_id=available_model,
        messages=[
            ChatMessage(role="user", content="Respond with the single word 'Sovereign'.")
        ],
        temperature=0.0,
        max_tokens=10,
    )

    resp = runtime.generate(req)

    assert resp is not None
    assert resp.content is not None and len(resp.content) > 0
    assert resp.model_id == available_model
    assert resp.usage is not None
    assert resp.usage.total_tokens > 0

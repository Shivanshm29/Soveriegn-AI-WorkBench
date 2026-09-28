"""Test Group E: Local runtime health check and availability."""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.health import HealthStatus
from backend.app.models.errors import ModelConfigurationError


def test_health_check_healthy():
    """Verify health check returns HEALTHY with available models when server responds with 200."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "object": "list",
        "data": [
            {"id": "Qwen/Qwen3-4B", "object": "model"},
            {"id": "Qwen/Qwen3-VL-4B-Instruct", "object": "model"},
        ],
    }

    with patch.object(httpx.Client, "get", return_value=mock_resp):
        health = runtime.health_check()
        assert health.status == HealthStatus.HEALTHY
        assert "Qwen/Qwen3-4B" in health.models
        assert "Qwen/Qwen3-VL-4B-Instruct" in health.models
        assert health.runtime == "vllm"
        assert health.base_url == "http://127.0.0.1:8000/v1"


def test_health_check_unavailable():
    """Verify health check returns UNAVAILABLE when connection is refused."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    with patch.object(
        httpx.Client,
        "get",
        side_effect=httpx.ConnectError("Connection refused on 127.0.0.1:8000"),
    ):
        health = runtime.health_check()
        assert health.status == HealthStatus.UNAVAILABLE
        assert "Connection refused" in health.error


def test_health_check_timeout():
    """Verify health check returns TIMEOUT when request times out."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1", health_timeout=2.0)

    with patch.object(
        httpx.Client,
        "get",
        side_effect=httpx.TimeoutException("Timed out"),
    ):
        health = runtime.health_check()
        assert health.status == HealthStatus.TIMEOUT
        assert "timed out" in health.error.lower()


def test_health_check_misconfigured():
    """Verify health check returns MISCONFIGURED when endpoint returns HTTP 404 or 500."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"

    with patch.object(httpx.Client, "get", return_value=mock_resp):
        health = runtime.health_check()
        assert health.status == HealthStatus.MISCONFIGURED
        assert "404" in health.error


def test_model_availability_distinction():
    """Verify model_available accurately checks whether model is installed vs merely registered."""
    runtime = LocalOpenAIRuntime(base_url="http://127.0.0.1:8000/v1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "object": "list",
        "data": [
            {"id": "Qwen/Qwen3-4B", "object": "model"},
        ],
    }

    with patch.object(httpx.Client, "get", return_value=mock_resp):
        # Qwen3-4B is present
        assert runtime.model_available("Qwen/Qwen3-4B") is True
        # Qwen3-30B-A3B is registered in high profile, but NOT installed in this server
        assert runtime.model_available("Qwen/Qwen3-30B-A3B") is False

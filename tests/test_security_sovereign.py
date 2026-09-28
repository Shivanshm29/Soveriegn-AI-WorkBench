"""Test Group F: Security and Sovereignty Policy."""

from unittest.mock import patch
import httpx
import pytest

from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.errors import ModelConfigurationError
from backend.app.security.network_policy import (
    validate_sovereign_url,
    SovereigntyViolationError,
)


def test_sovereign_allowed_destinations():
    """Verify local loopback and private LAN addresses are permitted in sovereign mode."""
    assert validate_sovereign_url("http://127.0.0.1:8000/v1", sovereign_mode=True) is True
    assert validate_sovereign_url("http://localhost:8000/v1", sovereign_mode=True) is True
    assert validate_sovereign_url("http://10.0.1.50:8000/v1", sovereign_mode=True) is True
    assert validate_sovereign_url("http://192.168.1.100:8000/v1", sovereign_mode=True) is True
    assert validate_sovereign_url("http://172.16.0.2:8000/v1", sovereign_mode=True) is True


def test_sovereign_rejected_external_destinations():
    """Verify public cloud domains and public IPs are strictly rejected without network access."""
    external_urls = [
        "https://api.openai.com/v1",
        "https://api.anthropic.com/v1",
        "https://generativelanguage.googleapis.com/v1",
        "http://8.8.8.8:8000/v1",
        "http://1.1.1.1:8000/v1",
        "https://cloud.example.org/api",
    ]

    for url in external_urls:
        with pytest.raises(SovereigntyViolationError):
            validate_sovereign_url(url, sovereign_mode=True)


def test_runtime_rejects_external_endpoint_before_network():
    """Verify LocalOpenAIRuntime immediately aborts construction for external URLs without hitting the network."""
    with patch.object(httpx.Client, "post") as mock_post:
        with patch.object(httpx.Client, "get") as mock_get:
            with pytest.raises(ModelConfigurationError) as exc_info:
                LocalOpenAIRuntime(
                    base_url="https://api.openai.com/v1",
                    sovereign_mode=True,
                )
            assert "Sovereignty violation" in str(exc_info.value)
            # Ensure zero network calls were made
            mock_post.assert_not_called()
            mock_get.assert_not_called()

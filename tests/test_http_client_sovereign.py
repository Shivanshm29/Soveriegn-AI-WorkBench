"""Phase 2 Tests: Sovereign HTTP Client, Redirect & Proxy Protection (Tests H & J)."""

import os
from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.security.http_client import SovereignHttpClient
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    SovereigntyViolationError,
)
from backend.app.config.settings import Settings


def test_http_client_allows_local_request():
    """Verify SovereignHttpClient permits local requests."""
    policy = SovereigntyPolicy(settings=Settings())
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_redirect = False
    mock_resp.text = '{"status": "ok"}'

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        with SovereignHttpClient(policy=policy) as client:
            resp = client.get("http://127.0.0.1:8000/v1/models")
            assert resp.status_code == 200


def test_http_client_blocks_external_request():
    """Verify SovereignHttpClient blocks external requests before dispatch."""
    policy = SovereigntyPolicy(settings=Settings())

    with patch.object(httpx.Client, "request") as mock_request:
        with SovereignHttpClient(policy=policy) as client:
            with pytest.raises(SovereigntyViolationError):
                client.get("https://api.openai.com/v1/chat/completions")
            # Ensure no network request was dispatched
            mock_request.assert_not_called()


def test_redirect_to_external_endpoint_blocked():
    """Test H: Verify HTTP 302/301 redirect to an external destination is caught and blocked."""
    policy = SovereigntyPolicy(settings=Settings())

    # Simulate local server returning a 302 redirect pointing to an external destination
    mock_redirect_resp = MagicMock(spec=httpx.Response)
    mock_redirect_resp.status_code = 302
    mock_redirect_resp.is_redirect = True
    mock_redirect_resp.url = httpx.URL("http://127.0.0.1:8000/v1/redirect-test")
    mock_redirect_resp.headers = {"location": "https://evil.com/exfiltrate"}

    with patch.object(httpx.Client, "request", return_value=mock_redirect_resp):
        with SovereignHttpClient(policy=policy) as client:
            with pytest.raises(SovereigntyViolationError) as exc_info:
                client.get("http://127.0.0.1:8000/v1/redirect-test")
            assert "evil.com" in str(exc_info.value) or "Sovereignty violation" in str(exc_info.value)


def test_proxy_environment_safety(monkeypatch):
    """Test J: Verify ambient environment proxy settings cannot bypass sovereign isolation."""
    monkeypatch.setenv("HTTP_PROXY", "http://external-proxy.example.com:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://external-proxy.example.com:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://external-proxy.example.com:1080")

    policy = SovereigntyPolicy(settings=Settings())
    client = SovereignHttpClient(policy=policy)

    # In sovereign mode, trust_env must be False to prevent traffic diversion
    assert client._client.trust_env is False
    client.close()

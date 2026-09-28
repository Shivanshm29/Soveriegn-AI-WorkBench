"""Phase 2 Acceptance Test Suite.

Verifies the 16 acceptance criteria for Sovereignty and Zero-Egress Boundary:
1. Phase 0 passes
2. Phase 1 passes
3. Sovereign configuration is valid
4. Invalid sovereign configurations are rejected
5. Local endpoints are allowed
6. External endpoints are blocked
7. Cloud model endpoints are blocked
8. No cloud fallback exists
9. URL bypasses are blocked
10. Redirect bypasses are blocked
11. Proxy bypass is addressed
12. Remote telemetry is disabled
13. Blocked egress creates a local audit event
14. Secrets are not logged
15. Unknown destinations fail closed
16. Sovereignty status is accurate
"""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.config.settings import Settings
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    SecurityState,
    SovereignConfigurationError,
    SovereigntyViolationError,
)
from backend.app.security.network_policy import NetworkPolicy
from backend.app.security.http_client import SovereignHttpClient
from backend.app.security.egress_sentinel import EgressSentinel
from backend.app.security.status_service import get_sovereign_status
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.registry import ModelRegistry
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.models.errors import ModelUnavailableError


def test_acceptance_01_phase_0_passes():
    """1. Verify Phase 0 contracts remain passing."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=False)
    registry = ModelRegistry(settings=settings)
    assert registry.active_profile_name == "small"
    assert registry.resolve_model_name("general_reasoning") == "Qwen/Qwen3-4B"


def test_acceptance_02_phase_1_passes():
    """2. Verify Phase 1 runtime contracts remain passing."""
    runtime = create_model_runtime()
    assert runtime is not None
    assert runtime.base_url == "http://127.0.0.1:8000/v1"
    assert "text" in runtime.capabilities()


def test_acceptance_03_sovereign_configuration_valid():
    """3. Verify default sovereign configuration is accepted."""
    settings = Settings()
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.SOVEREIGN
    assert policy.is_sovereign_mode() is True


def test_acceptance_04_invalid_configurations_rejected():
    """4. Verify invalid configurations (e.g. enabling cloud or telemetry) are rejected."""
    # Attempting cloud models
    pol_cloud = SovereigntyPolicy(settings=Settings(ALLOW_CLOUD_MODELS=True))
    with pytest.raises(SovereignConfigurationError):
        pol_cloud.validate_configuration()

    # Attempting remote telemetry
    pol_telemetry = SovereigntyPolicy(settings=Settings(ALLOW_REMOTE_TELEMETRY=True))
    with pytest.raises(SovereignConfigurationError):
        pol_telemetry.validate_configuration()

    # Attempting external network
    pol_net = SovereigntyPolicy(settings=Settings(ALLOW_EXTERNAL_NETWORK=True))
    with pytest.raises(SovereignConfigurationError):
        pol_net.validate_configuration()


def test_acceptance_05_local_endpoints_allowed():
    """5. Verify local endpoints (localhost, 127.0.0.1) are allowed."""
    policy = SovereigntyPolicy()
    assert policy.is_endpoint_allowed("http://localhost:8000/v1") is True
    assert policy.is_endpoint_allowed("http://127.0.0.1:8000/v1") is True


def test_acceptance_06_external_endpoints_blocked():
    """6. Verify external endpoints (example.com) are blocked."""
    policy = SovereigntyPolicy()
    assert policy.is_endpoint_allowed("https://example.com") is False
    with pytest.raises(SovereigntyViolationError):
        policy.validate_endpoint("https://example.com")


def test_acceptance_07_cloud_model_endpoints_blocked():
    """7. Verify cloud AI endpoints are blocked."""
    policy = SovereigntyPolicy()
    assert policy.is_endpoint_allowed("https://api.openai.com/v1") is False
    assert policy.is_endpoint_allowed("https://api.anthropic.com/v1") is False
    assert policy.is_endpoint_allowed("https://generativelanguage.googleapis.com/v1") is False


def test_acceptance_08_no_cloud_fallback():
    """8. Verify local inference failure does not trigger cloud fallback."""
    settings = Settings()
    runtime = create_model_runtime(settings)
    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Offline")):
        with pytest.raises(ModelUnavailableError):
            runtime.generate(ModelRequest(model_id="Qwen/Qwen3-4B", messages=[ChatMessage(role="user", content="hi")]))
    assert settings.ALLOW_CLOUD_MODELS is False


def test_acceptance_09_url_bypasses_blocked():
    """9. Verify host parsing cannot be tricked with subdomains or credentials."""
    net_policy = NetworkPolicy()
    assert net_policy.check_url("http://localhost.evil.com:8000").allowed is False
    assert net_policy.check_url("http://evil.com/localhost").allowed is False
    assert net_policy.check_url("http://localhost@evil.com").allowed is False


def test_acceptance_10_redirect_bypasses_blocked():
    """10. Verify redirects from local endpoints to external destinations are intercepted."""
    policy = SovereigntyPolicy()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 302
    mock_resp.is_redirect = True
    mock_resp.url = httpx.URL("http://127.0.0.1:8000/test")
    mock_resp.headers = {"location": "https://external-leak.com/exfiltrate"}

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        with SovereignHttpClient(policy=policy) as client:
            with pytest.raises(SovereigntyViolationError):
                client.get("http://127.0.0.1:8000/test")


def test_acceptance_11_proxy_bypass_addressed(monkeypatch):
    """11. Verify ambient HTTP proxies cannot redirect traffic."""
    monkeypatch.setenv("HTTP_PROXY", "http://corporate-proxy:8080")
    client = SovereignHttpClient()
    assert client._client.trust_env is False
    client.close()


def test_acceptance_12_remote_telemetry_disabled():
    """12. Verify remote telemetry is disabled by policy."""
    policy = SovereigntyPolicy()
    assert policy.is_remote_telemetry_allowed() is False


def test_acceptance_13_blocked_egress_creates_local_audit():
    """13. Verify blocked requests create an audit event and increment telemetry."""
    sentinel = EgressSentinel()
    policy = SovereigntyPolicy(sentinel=sentinel)
    with pytest.raises(SovereigntyViolationError):
        policy.validate_endpoint("https://unapproved.destination.com")
    assert sentinel.blocked_egress_attempts >= 1
    events = sentinel.get_events()
    assert any(e.event_type == "NETWORK_EGRESS_BLOCKED" for e in events)


def test_acceptance_14_secrets_not_logged():
    """14. Verify confidential tokens are never stored in audit reasons or components."""
    sentinel = EgressSentinel()
    policy = SovereigntyPolicy(sentinel=sentinel)
    with pytest.raises(SovereigntyViolationError):
        policy.validate_endpoint("https://bad.com?key=SECRET_TOKEN_XYZ", component="agent_runner")
    event = sentinel.get_events()[-1]
    assert "SECRET_TOKEN_XYZ" not in event.reason
    assert "SECRET_TOKEN_XYZ" not in event.component


def test_acceptance_15_unknown_destinations_fail_closed():
    """15. Verify unknown destinations fail closed."""
    policy = SovereigntyPolicy()
    assert policy.is_endpoint_allowed("http://unknown-host-12345.org") is False
    assert policy.is_endpoint_allowed("") is False


def test_acceptance_16_sovereignty_status_accurate():
    """16. Verify sovereignty status service reports accurate telemetry and configuration."""
    status = get_sovereign_status()
    assert status.sovereign_mode is True
    assert status.security_state == SecurityState.SOVEREIGN
    assert status.external_connections_successful == 0
    assert status.external_network_allowed is False
    assert status.cloud_models_allowed is False
    assert status.remote_telemetry_allowed is False

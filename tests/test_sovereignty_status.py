"""Phase 2 Tests: Sovereignty Status Service (Test M)."""

from backend.app.config.settings import Settings
from backend.app.security.status_service import get_sovereign_status, SovereignStatus
from backend.app.security.sovereignty_policy import SovereigntyPolicy, SecurityState
from backend.app.security.egress_sentinel import EgressSentinel


def test_sovereignty_status_service():
    """Test M: Verify status service accurately reports current security state and zero egress."""
    settings = Settings(
        SOVEREIGN_MODE=True,
        ALLOW_EXTERNAL_NETWORK=False,
        ALLOW_CLOUD_MODELS=False,
        ALLOW_REMOTE_TELEMETRY=False,
        USE_HIGH_LEVEL_MODELS=False,
    )
    sentinel = EgressSentinel(settings=settings)
    policy = SovereigntyPolicy(settings=settings, sentinel=sentinel)

    status = get_sovereign_status(settings=settings, policy=policy, sentinel=sentinel)

    assert isinstance(status, SovereignStatus)
    assert status.sovereign_mode is True
    assert status.security_state == SecurityState.SOVEREIGN
    assert status.external_network_allowed is False
    assert status.cloud_models_allowed is False
    assert status.remote_telemetry_allowed is False
    assert status.external_connections_successful == 0
    assert "localhost" in status.allowed_internal_hosts
    assert status.active_model_profile == "small"

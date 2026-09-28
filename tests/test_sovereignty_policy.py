"""Phase 2 Tests: Sovereignty Policy and Startup Validation (Tests B & C)."""

import pytest
from backend.app.config.settings import Settings
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    SecurityState,
    SovereignConfigurationError,
)
from backend.app.security.startup import validate_startup_sovereignty


def test_valid_sovereign_configuration():
    """Test B: Verify default sovereign configuration is valid and accepted."""
    settings = Settings(
        SOVEREIGN_MODE=True,
        ALLOW_EXTERNAL_NETWORK=False,
        ALLOW_CLOUD_MODELS=False,
        ALLOW_REMOTE_TELEMETRY=False,
    )
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.SOVEREIGN
    assert policy.is_sovereign_mode() is True
    assert policy.is_network_access_allowed() is False
    assert policy.is_cloud_models_allowed() is False
    assert policy.is_remote_telemetry_allowed() is False
    # Startup validation succeeds
    validate_startup_sovereignty(settings)


def test_reject_cloud_models_in_sovereign_workbench():
    """Test C1: Verify attempting to enable cloud models is rejected."""
    settings = Settings(
        SOVEREIGN_MODE=True,
        ALLOW_CLOUD_MODELS=True,
    )
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.INVALID_CONFIGURATION

    with pytest.raises(SovereignConfigurationError) as exc_info:
        policy.validate_configuration()
    assert "ALLOW_CLOUD_MODELS must be false" in str(exc_info.value)


def test_reject_remote_telemetry():
    """Test C2: Verify attempting to enable remote telemetry is rejected."""
    settings = Settings(
        SOVEREIGN_MODE=True,
        ALLOW_REMOTE_TELEMETRY=True,
    )
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.INVALID_CONFIGURATION

    with pytest.raises(SovereignConfigurationError) as exc_info:
        policy.validate_configuration()
    assert "ALLOW_REMOTE_TELEMETRY must be false" in str(exc_info.value)


def test_reject_unrestricted_external_network():
    """Test C3: Verify attempting to enable external network is rejected."""
    settings = Settings(
        SOVEREIGN_MODE=True,
        ALLOW_EXTERNAL_NETWORK=True,
    )
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.INVALID_CONFIGURATION

    with pytest.raises(SovereignConfigurationError) as exc_info:
        policy.validate_configuration()
    assert "ALLOW_EXTERNAL_NETWORK must be false" in str(exc_info.value)


def test_reject_disabling_sovereignty():
    """Test C4: Verify system rejects any attempt to turn off sovereign air-gap."""
    settings = Settings(
        SOVEREIGN_MODE=False,
    )
    policy = SovereigntyPolicy(settings=settings)
    assert policy.get_security_state() == SecurityState.INVALID_CONFIGURATION

    with pytest.raises(SovereignConfigurationError) as exc_info:
        policy.validate_configuration()
    assert "SOVEREIGN_MODE must be true" in str(exc_info.value)

"""Application startup validation for sovereign security posture."""

from typing import Optional
from backend.app.config.settings import Settings, get_settings
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    SovereignConfigurationError,
    get_sovereignty_policy,
)


def validate_startup_sovereignty(settings: Optional[Settings] = None) -> None:
    """Validate configuration on application startup.

    Raises SovereignConfigurationError if any setting attempts to breach
    the permanent local air-gap boundary.
    """
    cfg = settings or get_settings()
    policy = SovereigntyPolicy(settings=cfg)
    policy.validate_configuration()

    # Also validate that the configured local model base URL is permitted
    if cfg.MODEL_BASE_URL:
        policy.validate_endpoint(cfg.MODEL_BASE_URL, component="startup_probe")

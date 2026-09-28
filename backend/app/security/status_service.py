"""Sovereignty status service.

Reports real-time sovereignty, security posture, and egress telemetry metrics.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.config.settings import Settings, get_settings
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    get_sovereignty_policy,
    SecurityState,
)
from backend.app.security.egress_sentinel import (
    EgressSentinel,
    get_egress_sentinel,
)


class SovereignStatus(BaseModel):
    """Structured status reporting permanent local zero-egress state."""

    sovereign_mode: bool
    security_state: SecurityState
    external_network_allowed: bool
    cloud_models_allowed: bool
    remote_telemetry_allowed: bool
    allowed_internal_hosts: List[str]
    external_connections_successful: int
    blocked_egress_attempts: int
    allowed_local_requests: int
    active_model_profile: str


def get_sovereign_status(
    settings: Optional[Settings] = None,
    policy: Optional[SovereigntyPolicy] = None,
    sentinel: Optional[EgressSentinel] = None,
) -> SovereignStatus:
    """Retrieve current sovereignty status and egress telemetry."""
    cfg = settings or get_settings()
    pol = policy or get_sovereignty_policy(cfg)
    sen = sentinel or get_egress_sentinel(cfg)

    telemetry = sen.get_telemetry()
    active_profile = "high" if cfg.USE_HIGH_LEVEL_MODELS else "small"

    return SovereignStatus(
        sovereign_mode=pol.is_sovereign_mode(),
        security_state=pol.get_security_state(),
        external_network_allowed=pol.is_network_access_allowed(),
        cloud_models_allowed=pol.is_cloud_models_allowed(),
        remote_telemetry_allowed=pol.is_remote_telemetry_allowed(),
        allowed_internal_hosts=list(pol.network_policy.allowed_hosts),
        external_connections_successful=telemetry["external_connections_successful"],
        blocked_egress_attempts=telemetry["blocked_egress_attempts"],
        allowed_local_requests=telemetry["allowed_local_requests"],
        active_model_profile=active_profile,
    )

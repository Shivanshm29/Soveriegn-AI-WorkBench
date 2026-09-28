"""Central Sovereignty Policy for the Sovereign Workbench.

Authoritative decision maker guaranteeing permanent local air-gapped isolation,
zero cloud fallback, and zero remote egress.
"""

from enum import Enum
from typing import Optional, List
from backend.app.config.settings import Settings, get_settings
from backend.app.security.network_policy import (
    NetworkPolicy,
    NetworkDecision,
    SovereigntyViolationError,
    get_network_policy,
)
from backend.app.security.egress_sentinel import EgressSentinel, get_egress_sentinel


class SecurityState(str, Enum):
    """Sovereign security operational states."""

    SOVEREIGN = "SOVEREIGN"
    NON_SOVEREIGN = "NON_SOVEREIGN"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


class SovereignConfigurationError(Exception):
    """Raised when application configuration violates sovereign air-gap rules."""
    pass


class SovereigntyPolicy:
    """Central authority governing sovereign air-gap rules."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        sentinel: Optional[EgressSentinel] = None,
        network_policy: Optional[NetworkPolicy] = None,
    ):
        self.settings = settings or get_settings()
        self.sentinel = sentinel or get_egress_sentinel(self.settings)

        allowed_hosts = getattr(self.settings, "ALLOWED_INTERNAL_HOSTS", None)
        self.network_policy = network_policy or get_network_policy(allowed_hosts=allowed_hosts)

    def is_sovereign_mode(self) -> bool:
        """Sovereign mode is always permanently enabled by architectural invariant."""
        return self.settings.SOVEREIGN_MODE

    def is_network_access_allowed(self) -> bool:
        """External network connectivity is strictly forbidden."""
        return self.settings.ALLOW_EXTERNAL_NETWORK

    def is_cloud_models_allowed(self) -> bool:
        """Cloud models are never permitted in the sovereign workbench."""
        return self.settings.ALLOW_CLOUD_MODELS

    def is_remote_telemetry_allowed(self) -> bool:
        """Remote telemetry transmission is strictly forbidden."""
        return self.settings.ALLOW_REMOTE_TELEMETRY

    def get_security_state(self) -> SecurityState:
        """Evaluate configuration and determine active security state."""
        # Any attempt to enable external network, cloud models, or remote telemetry is invalid
        if (
            not self.settings.SOVEREIGN_MODE
            or self.settings.ALLOW_EXTERNAL_NETWORK
            or self.settings.ALLOW_CLOUD_MODELS
            or self.settings.ALLOW_REMOTE_TELEMETRY
        ):
            return SecurityState.INVALID_CONFIGURATION

        return SecurityState.SOVEREIGN

    def validate_configuration(self) -> None:
        """Validate startup configuration.

        Fails fast if the environment violates the permanent air-gap model.
        """
        state = self.get_security_state()
        if state == SecurityState.INVALID_CONFIGURATION:
            violations = []
            if not self.settings.SOVEREIGN_MODE:
                violations.append("SOVEREIGN_MODE must be true (system is permanently air-gapped).")
            if self.settings.ALLOW_EXTERNAL_NETWORK:
                violations.append("ALLOW_EXTERNAL_NETWORK must be false.")
            if self.settings.ALLOW_CLOUD_MODELS:
                violations.append("ALLOW_CLOUD_MODELS must be false.")
            if self.settings.ALLOW_REMOTE_TELEMETRY:
                violations.append("ALLOW_REMOTE_TELEMETRY must be false.")

            error_msg = f"Invalid sovereign configuration: {'; '.join(violations)}"
            raise SovereignConfigurationError(error_msg)

    def is_endpoint_allowed(self, url_or_host: str) -> bool:
        """Query whether an endpoint is permitted without throwing an exception."""
        if "://" in url_or_host:
            decision = self.network_policy.check_url(url_or_host)
        else:
            decision = self.network_policy.check_host(url_or_host)
        return decision.allowed

    def validate_endpoint(
        self,
        url: str,
        component: str = "app",
        task_id: Optional[str] = None,
    ) -> NetworkDecision:
        """Validate an outbound URL.

        Records decision in the EgressSentinel and raises SovereigntyViolationError
        if denied.
        """
        decision = self.network_policy.check_url(url, component=component)
        self.sentinel.record_decision(decision, task_id=task_id)

        if not decision.allowed:
            raise SovereigntyViolationError(decision.reason, decision=decision)

        return decision

    def explain_decision(self, decision: NetworkDecision) -> str:
        """Produce human-readable explanation of an access decision."""
        status = "ALLOWED" if decision.allowed else "BLOCKED"
        return f"[{status}] Destination '{decision.destination}': {decision.reason} (Component: {decision.component})"


# Global singleton instance
_global_policy: Optional[SovereigntyPolicy] = None


def get_sovereignty_policy(settings: Optional[Settings] = None) -> SovereigntyPolicy:
    """Obtain or initialize global SovereigntyPolicy."""
    global _global_policy
    if _global_policy is None or settings is not None:
        _global_policy = SovereigntyPolicy(settings=settings)
    return _global_policy

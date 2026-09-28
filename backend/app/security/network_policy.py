"""Sovereign network policy enforcement.

Ensures that model runtime endpoints and other system network requests adhere
to permanent local-only zero-egress isolation rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
from typing import List, Optional
from urllib.parse import urlparse


class SovereigntyViolationError(Exception):
    """Raised when a network request or configuration violates sovereign zero-egress policy."""

    def __init__(self, message: str, decision: Optional["NetworkDecision"] = None):
        super().__init__(message)
        self.message = message
        self.decision = decision


@dataclass
class NetworkDecision:
    """Structured decision returned by the network policy."""

    allowed: bool
    destination: str
    host: str
    port: Optional[int]
    reason: str
    policy_name: str = "permanent_local_only"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    component: str = "app"


class NetworkPolicy:
    """Central network policy enforcing permanent local-only communication."""

    DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "::1"]

    def __init__(self, allowed_hosts: Optional[List[str]] = None):
        if allowed_hosts:
            self.allowed_hosts = set(h.strip().lower() for h in allowed_hosts if h.strip())
        else:
            self.allowed_hosts = set(self.DEFAULT_ALLOWED_HOSTS)

    def check_host(
        self,
        host: str,
        port: Optional[int] = None,
        component: str = "app",
    ) -> NetworkDecision:
        """Check if a raw hostname or IP address is allowed.

        Fail-closed: Any host not explicitly allowed is rejected.
        """
        if not host:
            return NetworkDecision(
                allowed=False,
                destination=f"{host}:{port}" if port else "",
                host="",
                port=port,
                reason="Empty or missing host is forbidden.",
                component=component,
            )

        norm_host = host.strip().lower()

        # Check explicit allowlist
        if norm_host in self.allowed_hosts:
            return NetworkDecision(
                allowed=True,
                destination=f"{norm_host}:{port}" if port else norm_host,
                host=norm_host,
                port=port,
                reason=f"Host '{norm_host}' is in the approved local allowlist.",
                component=component,
            )

        # Check local domain extensions (.localhost, .local)
        if norm_host.endswith(".localhost") or norm_host.endswith(".local"):
            return NetworkDecision(
                allowed=True,
                destination=f"{norm_host}:{port}" if port else norm_host,
                host=norm_host,
                port=port,
                reason=f"Host '{norm_host}' is an approved local domain.",
                component=component,
            )

        # Check if it's an IP address and verify loopback or private LAN (RFC 1918)
        try:
            ip = ipaddress.ip_address(norm_host)
            if ip.is_loopback or ip.is_private or ip.is_link_local:
                return NetworkDecision(
                    allowed=True,
                    destination=f"{norm_host}:{port}" if port else norm_host,
                    host=norm_host,
                    port=port,
                    reason=f"IP '{norm_host}' is an approved local/private address.",
                    component=component,
                )
        except ValueError:
            pass

        # Fail closed on all external, public, or unapproved domains/IPs
        return NetworkDecision(
            allowed=False,
            destination=f"{norm_host}:{port}" if port else norm_host,
            host=norm_host,
            port=port,
            reason=f"Sovereignty violation: Destination '{norm_host}' is not permitted under zero-egress policy.",
            component=component,
        )

    def check_url(self, url: str, component: str = "app") -> NetworkDecision:
        """Check whether a full URL points to an approved local endpoint.

        Parses URL strictly to prevent bypass tricks (e.g., localhost.evil.com, evil.com/localhost, user@evil.com).
        """
        if not url:
            return NetworkDecision(
                allowed=False,
                destination="",
                host="",
                port=None,
                reason="URL cannot be empty.",
                component=component,
            )

        try:
            parsed = urlparse(url)
        except Exception as e:
            return NetworkDecision(
                allowed=False,
                destination=url,
                host="",
                port=None,
                reason=f"Malformed URL: {e}",
                component=component,
            )

        if parsed.scheme not in ("http", "https"):
            return NetworkDecision(
                allowed=False,
                destination=url,
                host=parsed.hostname or "",
                port=parsed.port,
                reason=f"Forbidden URL scheme '{parsed.scheme}'. Only local http/https permitted.",
                component=component,
            )

        hostname = parsed.hostname
        if not hostname:
            return NetworkDecision(
                allowed=False,
                destination=url,
                host="",
                port=parsed.port,
                reason="Could not extract valid hostname from URL.",
                component=component,
            )

        # Re-check hostname through check_host
        decision = self.check_host(hostname, parsed.port, component=component)
        # Update destination to full URL for context
        decision.destination = url
        return decision


# Global default instance
_default_network_policy = NetworkPolicy()


def get_network_policy(allowed_hosts: Optional[List[str]] = None) -> NetworkPolicy:
    """Obtain NetworkPolicy instance."""
    if allowed_hosts:
        return NetworkPolicy(allowed_hosts=allowed_hosts)
    return _default_network_policy


def is_local_or_private_host(hostname: str) -> bool:
    """Check if a hostname or IP address is allowed local loopback."""
    decision = _default_network_policy.check_host(hostname)
    return decision.allowed


def validate_sovereign_url(url: str, sovereign_mode: bool = True) -> bool:
    """Validate whether an endpoint URL is permitted under permanent local zero-egress.

    Raises SovereigntyViolationError if the URL violates the policy.
    Maintained for backward compatibility with Phase 1 components.
    """
    decision = _default_network_policy.check_url(url)
    if not decision.allowed:
        raise SovereigntyViolationError(decision.reason, decision=decision)
    return True

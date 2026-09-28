"""Sovereign network policy enforcement.

Ensures that model runtime endpoints and other system network requests adhere
to zero-egress / sovereign isolation rules.
"""

import ipaddress
import socket
from urllib.parse import urlparse


class SovereigntyViolationError(Exception):
    """Raised when a network request or configuration violates sovereign zero-egress policy."""
    pass


def is_local_or_private_host(hostname: str) -> bool:
    """Check if a hostname or IP address is local loopback or private LAN."""
    if not hostname:
        return False

    # Standard loopback names
    normalized = hostname.strip().lower()
    if normalized in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    if normalized.endswith(".localhost") or normalized.endswith(".local"):
        return True

    # Check if host is an IP address
    try:
        ip = ipaddress.ip_address(normalized)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        pass

    # For safety in strict sovereign mode:
    # Any external unresolved domain name is NOT local/private.
    # Note: We do NOT perform DNS resolution to remote DNS in sovereign mode to prevent DNS leakage.
    return False


def validate_sovereign_url(url: str, sovereign_mode: bool = True) -> bool:
    """Validate whether an endpoint URL is permitted under sovereign mode.

    If sovereign_mode is True, requires the host to be loopback (127.0.0.1, localhost)
    or private local network.
    Raises SovereigntyViolationError if the URL violates the policy.
    """
    if not url:
        raise SovereigntyViolationError("Model endpoint URL cannot be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SovereigntyViolationError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SovereigntyViolationError(f"Could not parse hostname from URL '{url}'.")

    if sovereign_mode:
        if not is_local_or_private_host(hostname):
            raise SovereigntyViolationError(
                f"Sovereignty violation: External host '{hostname}' is not permitted when SOVEREIGN_MODE=true. "
                f"Only local/private endpoints (e.g., 127.0.0.1, localhost, private LAN) are allowed."
            )

    return True

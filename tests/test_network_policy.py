"""Phase 2 Tests: Network Policy and Host Validation (Tests D, E, F, G, L)."""

import pytest
from backend.app.security.network_policy import NetworkPolicy, SovereigntyViolationError


@pytest.fixture
def policy():
    return NetworkPolicy(allowed_hosts=["localhost", "127.0.0.1", "::1"])


def test_local_endpoints_allowed(policy):
    """Test D: Verify localhost and 127.0.0.1 and ::1 are permitted."""
    d1 = policy.check_url("http://localhost:8000/v1/chat/completions")
    assert d1.allowed is True
    assert d1.host == "localhost"

    d2 = policy.check_url("http://127.0.0.1:8000/v1/models")
    assert d2.allowed is True
    assert d2.host == "127.0.0.1"

    d3 = policy.check_host("127.0.0.1", port=8000)
    assert d3.allowed is True

    d4 = policy.check_host("::1")
    assert d4.allowed is True


def test_external_endpoint_denied(policy):
    """Test E: Verify external public websites are denied before network dispatch."""
    decision = policy.check_url("https://example.com/api")
    assert decision.allowed is False
    assert "Sovereignty violation" in decision.reason
    assert decision.host == "example.com"


def test_cloud_ai_endpoints_denied(policy):
    """Test F: Verify cloud AI provider endpoints are strictly blocked."""
    cloud_endpoints = [
        "https://api.openai.com/v1/chat/completions",
        "https://api.anthropic.com/v1/messages",
        "https://generativelanguage.googleapis.com/v1beta/models",
        "https://api.together.xyz/v1",
        "https://api.groq.com/openai/v1",
    ]
    for url in cloud_endpoints:
        decision = policy.check_url(url)
        assert decision.allowed is False
        assert "Sovereignty violation" in decision.reason


def test_url_bypass_tricks_denied(policy):
    """Test G: Verify URL bypass techniques attempting to mimic localhost are blocked."""
    bypass_attempts = [
        # Subdomain of evil domain
        "http://localhost.evil.com:8000/v1",
        # Path looking like localhost
        "http://evil.com/localhost",
        # Userinfo embedding
        "http://localhost@evil.com",
        "http://localhost:password@evil.com/v1",
        # IP prefix trick
        "http://127.0.0.1.nip.io:8000",
        # Mixed authority tricks
        "http://evil.com#localhost",
        "http://evil.com?ref=localhost",
    ]

    for url in bypass_attempts:
        decision = policy.check_url(url)
        assert decision.allowed is False, f"Bypass succeeded unexpectedly on: {url}"


def test_fail_closed_behavior(policy):
    """Test L: Verify unknown, malformed, empty, or non-http destinations fail closed (DENY)."""
    invalid_targets = [
        "",
        "   ",
        "ftp://localhost:21/file",
        "file:///etc/passwd",
        "http://",
        "not_a_valid_url",
        "http://[invalid_ipv6",
    ]

    for target in invalid_targets:
        decision = policy.check_url(target)
        assert decision.allowed is False, f"Invalid destination unexpectedly allowed: {target}"

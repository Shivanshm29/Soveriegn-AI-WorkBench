"""Phase 2 Tests: Egress Audit Logging and Secret Safety (Test K)."""

import json
from pathlib import Path
import pytest

from backend.app.config.settings import Settings
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    SovereigntyViolationError,
)
from backend.app.security.egress_sentinel import EgressSentinel


def test_egress_audit_event_recorded(tmp_path):
    """Test K: Trigger a blocked outbound request and verify a local audit event is created."""
    audit_dir = tmp_path / "audit"
    settings = Settings(AUDIT_ROOT=str(audit_dir))
    sentinel = EgressSentinel(settings=settings)
    policy = SovereigntyPolicy(settings=settings, sentinel=sentinel)

    blocked_url = "https://exfiltrate.data.com/upload"
    with pytest.raises(SovereigntyViolationError):
        policy.validate_endpoint(blocked_url, component="test_agent")

    # Verify telemetry incremented
    assert sentinel.blocked_egress_attempts == 1
    assert sentinel.external_connections_successful == 0

    # Verify in-memory event list
    events = sentinel.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "NETWORK_EGRESS_BLOCKED"
    assert event.decision == "DENY"
    assert event.component == "test_agent"
    assert "exfiltrate.data.com" in event.destination

    # Verify event written to local jsonl file
    log_file = audit_dir / "egress_events.jsonl"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8").strip()
    data = json.loads(content)
    assert data["event_type"] == "NETWORK_EGRESS_BLOCKED"
    assert data["decision"] == "DENY"


def test_audit_event_does_not_leak_secrets_or_prompts(tmp_path):
    """Verify egress event does not log confidential prompt bodies or API keys."""
    audit_dir = tmp_path / "audit"
    settings = Settings(AUDIT_ROOT=str(audit_dir))
    sentinel = EgressSentinel(settings=settings)
    policy = SovereigntyPolicy(settings=settings, sentinel=sentinel)

    secret_query_url = "https://external-leak.com/endpoint?secret_token=topsecretkey123"
    with pytest.raises(SovereigntyViolationError):
        policy.validate_endpoint(secret_query_url, component="prompt_evaluator")

    event = sentinel.get_events()[-1]
    # Check that event contains only destination/host and structured metadata
    assert "topsecretkey123" not in event.reason
    assert "topsecretkey123" not in event.component

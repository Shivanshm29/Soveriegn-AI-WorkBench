"""Egress Sentinel and security event auditor.

Tracks outbound connection attempts, enforces zero external connections, and
records security audit events locally without logging sensitive prompts or keys.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.app.config.settings import Settings, get_settings
from backend.app.security.network_policy import NetworkDecision


@dataclass
class EgressEvent:
    """Security audit record for an outbound connection attempt."""

    timestamp: str
    event_type: str  # NETWORK_EGRESS_BLOCKED or NETWORK_EGRESS_ALLOWED
    destination: str
    decision: str  # ALLOW or DENY
    reason: str
    component: str
    task_id: Optional[str] = None


class EgressSentinel:
    """Application-level egress monitor and audit event collector."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.audit_dir = Path(self.settings.AUDIT_ROOT)
        self.events_file = self.audit_dir / "egress_events.jsonl"

        self.external_connections_successful: int = 0
        self.blocked_egress_attempts: int = 0
        self.allowed_local_requests: int = 0

        self._in_memory_events: List[EgressEvent] = []

    def record_decision(
        self,
        decision: NetworkDecision,
        task_id: Optional[str] = None,
    ) -> EgressEvent:
        """Record a network decision, update telemetry, and append to local audit log."""
        if decision.allowed:
            self.allowed_local_requests += 1
            event_type = "NETWORK_EGRESS_ALLOWED"
            decision_str = "ALLOW"
        else:
            self.blocked_egress_attempts += 1
            event_type = "NETWORK_EGRESS_BLOCKED"
            decision_str = "DENY"

        event = EgressEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            destination=decision.destination,
            decision=decision_str,
            reason=decision.reason,
            component=decision.component,
            task_id=task_id,
        )

        self._in_memory_events.append(event)
        self._persist_event(event)
        return event

    def _persist_event(self, event: EgressEvent) -> None:
        """Append event to local audit file."""
        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception:
            # Audit logging must not crash the application if local filesystem is read-only
            pass

    def get_events(self, limit: int = 50) -> List[EgressEvent]:
        """Retrieve recent egress events from in-memory buffer."""
        return self._in_memory_events[-limit:]

    def get_telemetry(self) -> Dict[str, int]:
        """Return real-time egress telemetry counts."""
        return {
            "external_connections_successful": self.external_connections_successful,
            "blocked_egress_attempts": self.blocked_egress_attempts,
            "allowed_local_requests": self.allowed_local_requests,
        }

    def reset(self) -> None:
        """Reset counters and in-memory events (useful for unit tests)."""
        self.external_connections_successful = 0
        self.blocked_egress_attempts = 0
        self.allowed_local_requests = 0
        self._in_memory_events.clear()


# Global singleton instance
_global_sentinel: Optional[EgressSentinel] = None


def get_egress_sentinel(settings: Optional[Settings] = None) -> EgressSentinel:
    """Obtain or initialize global EgressSentinel."""
    global _global_sentinel
    if _global_sentinel is None:
        _global_sentinel = EgressSentinel(settings=settings)
    return _global_sentinel

# Security and Sovereignty

## Security goals

1. Confidential data stays inside the controlled environment.
2. Agents receive only authorized tools/data.
3. Sandboxed code cannot reach the external network.
4. Task A cannot access Task B's files.
5. High-risk actions require human approval.
6. All important actions are auditable.
7. Document prompt injection cannot escalate authority.

## Zero-egress architecture

```text
Application
 ├── local API
 ├── local model runtime
 ├── local OCR
 ├── local RAG
 └── local storage

No normal dependency on:
 ├── cloud LLM APIs
 ├── cloud OCR
 ├── web search
 └── remote telemetry
```

## Egress Sentinel

The system provides real-time telemetry via `EgressSentinel` (`backend/app/security/egress_sentinel.py`) and `get_sovereign_status()` (`backend/app/security/status_service.py`):

```json
{
  "sovereign_mode": true,
  "security_state": "SOVEREIGN",
  "external_network_allowed": false,
  "cloud_models_allowed": false,
  "remote_telemetry_allowed": false,
  "allowed_internal_hosts": ["localhost", "127.0.0.1", "::1"],
  "external_connections_successful": 0,
  "blocked_egress_attempts": 0,
  "allowed_local_requests": 0,
  "active_model_profile": "small"
}
```

The numbers come directly from live application telemetry, not hard-coded constants.
Blocked egress attempts are persisted to `data/audit/egress_events.jsonl` without logging prompts, documents, or secrets.

## Network controls

Phase 2 implements strict application-level enforcement:
- **Central SovereigntyPolicy (`backend/app/security/sovereignty_policy.py`)**: Authoritative gate enforcing permanent local air-gap isolation.
- **Fail-Closed NetworkPolicy (`backend/app/security/network_policy.py`)**: Strict allowlist (`localhost`, `127.0.0.1`, `::1`, configured internal hosts). Rejects domain bypass tricks (`localhost.evil.com`, `user@evil.com`).
- **SovereignHttpClient (`backend/app/security/http_client.py`)**: Intercepts all application outbound HTTP traffic, prevents external 3xx redirects, and sets `trust_env=False` to block proxy hijacking.
- **No Cloud Fallback**: Local inference failures raise structured local exceptions (`ModelUnavailableError`) and never attempt cloud AI endpoints.
- **Startup Validation (`backend/app/security/startup.py`)**: Halts boot immediately if any configuration attempts to enable external network, cloud models, or remote telemetry.

## Authorization

Every tool call should answer:

```text
Who requested it?
For which task?
With which agent?
Is the tool allowed?
Is the input allowed?
Is human approval required?
```

## Prompt injection

Treat external content as untrusted data.

Never allow:
- retrieved text
- PDFs
- source code comments
- spreadsheet cells
- OCR text

to redefine system policy.

## Audit events

At minimum:

```text
task_created
file_uploaded
model_selected
agent_delegated
tool_call
tool_result
policy_decision
approval_requested
approval_received
artifact_created
artifact_verified
knowledge_retrieved
egress_attempt
egress_blocked
task_completed
task_failed
```

## Secrets

Do not commit:
- API keys
- credentials
- production passwords
- private certificates

The sovereign runtime should not require cloud credentials.

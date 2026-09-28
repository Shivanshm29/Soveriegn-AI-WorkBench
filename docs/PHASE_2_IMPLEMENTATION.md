# Phase 2 Implementation: Sovereignty / Zero-Egress

## 1. Permanent Local Isolation (No Optional Sovereign Mode)

The workbench is an on-premise, air-gapped confidential knowledge platform. As established by architectural invariant, **there is no optional non-sovereign mode**. The workbench is permanently local, always disconnected from the internet, and enforces zero egress at all times.

The architecture strictly follows:
```text
                 Application
                     |
                     v
              Sovereignty Gate
                     |
          +----------+----------+
          |          |          |
          v          v          v
       Models      Tools      Services
          |          |          |
          +----------+----------+
                     |
                     v
               Egress Policy
                     |
              ALLOWED / BLOCKED
```

---

## 2. Central Sovereignty & Network Policy Layer

### 2.1 Central Sovereignty Policy (`backend/app/security/sovereignty_policy.py`)
- Authoritative singleton managing system security posture.
- Enforces:
  - `is_network_access_allowed() -> False`
  - `is_cloud_models_allowed() -> False`
  - `is_remote_telemetry_allowed() -> False`
  - `validate_configuration()`: Halts boot immediately if any environment toggle attempts to breach the air-gap.
  - `validate_endpoint(url, component)`: Central dispatch validator, recording all egress decisions in `EgressSentinel` and raising `SovereigntyViolationError` on unapproved destinations.

### 2.2 Network Policy & Fail-Closed Allowlisting (`backend/app/security/network_policy.py`)
- **Explicit Allowlist**: Only explicitly designated local hosts (`localhost`, `127.0.0.1`, `::1`, and configured internal hosts via `ALLOWED_INTERNAL_HOSTS`) are reachable.
- **Fail-Closed Rule**: Any unknown, unresolvable, external, or malformed destination is denied (`UNKNOWN => DENY`).
- **Bypass Prevention**:
  - Rejects subdomain spoofs (e.g., `localhost.evil.com`).
  - Rejects path spoofs (e.g., `evil.com/localhost`).
  - Rejects userinfo embedding (e.g., `localhost@evil.com`).
  - Rejects wildcard IP mapping tricks (e.g., `127.0.0.1.nip.io`).

---

## 3. Active Interception, Redirect & Proxy Protection

### 3.1 Sovereign HTTP Client (`backend/app/security/http_client.py`)
- Central client wrapping `httpx.Client`.
- **Pre-validation**: Calls `policy.validate_endpoint()` before sending any bytes to the network.
- **Redirect Protection**: Intercepts HTTP 3xx responses. If a local server returns a `Location` redirect pointing to an external destination, the client catches it and raises `SovereigntyViolationError` before following the redirect.
- **Proxy Protection**: Forces `trust_env=False`, completely ignoring ambient `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` environment variables to prevent accidental or malicious traffic diversion.
- **No Cloud Fallback**: On local inference failure, raises `ModelUnavailableError` cleanly; never contacts cloud AI providers.

---

## 4. Egress Sentinel & Audit Logging

### 4.1 Real-Time Egress Sentinel (`backend/app/security/egress_sentinel.py`)
- Tracks all connection attempts initiated across the workbench.
- Telemetry metrics:
  - `external_connections_successful: 0` (strictly enforced invariant)
  - `blocked_egress_attempts`
  - `allowed_local_requests`
- Appends security audit events to `data/audit/egress_events.jsonl`.
- **Zero Sensitive Data Invariant**: Logs only destination, decision, reason, component, and timestamp. Strictly forbids logging prompts, task documents, API keys, or full request payloads.

### 4.2 Sovereignty Status Service (`backend/app/security/status_service.py`)
- Exposes `get_sovereign_status()` returning structured status matching `API_CONTRACTS.md`:
  `sovereign_mode`, `security_state`, `external_network_allowed`, `cloud_models_allowed`, `remote_telemetry_allowed`, `allowed_internal_hosts`, telemetry counts, and active profile.

### 4.3 Startup Validation (`backend/app/security/startup.py`)
- `validate_startup_sovereignty()`:
  - Runs upon application boot.
  - Rejects configurations attempting to set `ALLOW_EXTERNAL_NETWORK=true`, `ALLOW_CLOUD_MODELS=true`, `ALLOW_REMOTE_TELEMETRY=true`, or `SOVEREIGN_MODE=false`.

---

## 5. Tests Run and Results

All 81 tests were executed via `python -m pytest tests/ -v`:

```text
======================== 80 passed, 1 skipped in 8.72s ========================
```

### Breakdown of Test Suites:
- **Phase 0 Contracts (5 tests)**: `tests/test_phase_0.py` — `PASS`
- **Phase 1 Runtime Architecture (41 tests)**:
  - `tests/test_runtime_construction.py` (5 tests) — `PASS`
  - `tests/test_mocked_runtime.py` (11 tests) — `PASS`
  - `tests/test_health_check.py` (5 tests) — `PASS`
  - `tests/test_security_sovereign.py` (3 tests) — `PASS`
  - `tests/test_profile_independence.py` (3 tests) — `PASS`
  - `tests/test_cloud_dependency.py` (2 tests) — `PASS`
  - `tests/test_hardware.py` (2 tests) — `PASS`
  - `tests/acceptance/test_phase_1_acceptance.py` (10 tests) — `PASS`
  - `tests/integration/test_local_endpoint.py` (1 test) — `SKIPPED` (no live vLLM server, cleanly skipped without fake pass)
- **Phase 2 Sovereignty & Zero-Egress (35 tests)**:
  - `tests/test_sovereignty_policy.py` (5 tests) — `PASS` (Tests B & C)
  - `tests/test_network_policy.py` (5 tests) — `PASS` (Tests D, E, F, G, L)
  - `tests/test_http_client_sovereign.py` (4 tests) — `PASS` (Tests H & J)
  - `tests/test_no_cloud_fallback.py` (1 test) — `PASS` (Test I)
  - `tests/test_egress_audit.py` (2 tests) — `PASS` (Test K)
  - `tests/test_sovereignty_status.py` (1 test) — `PASS` (Test M)
  - `tests/acceptance/test_phase_2_acceptance.py` (16 tests) — `PASS` (Criteria 1–16)

---

## 6. Security Code Review

Grep auditing across `backend/app/`:
- `requests`: 0 usages.
- `httpx`: Used exclusively in `SovereignHttpClient` and `LocalOpenAIRuntime`, both gated by `SovereigntyPolicy.validate_endpoint()`, `trust_env=False`, and redirect validation.
- `aiohttp`: 0 usages.
- `urllib`: Used exclusively for URL parsing (`urlparse`, `urljoin`). Zero outbound network calls.
- `socket`: 0 raw socket connections.
- `websocket`: 0 usages.
- Cloud AI Endpoints (`api.openai.com`, Anthropic, Gemini): 0 occurrences in backend source.

---

## 7. Known Limitations

1. Network policies operate at the application layer. Infrastructure-level isolation (Docker network disabled, host firewall rules) will be integrated in Phase 9 for the coding sandbox.
2. The real local vLLM integration test is skipped when no local model server is actively serving on port 8000.

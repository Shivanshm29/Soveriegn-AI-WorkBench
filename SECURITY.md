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

The UI should show:

```text
SOVEREIGN MODE: ON

External connections
Successful: 0
Blocked: 0
Unexpected: 0
```

The numbers must come from actual telemetry, not a hard-coded label.

## Network controls

Use defense in depth:
- application-level allowlist
- container network isolation
- host firewall
- sandbox network disabled
- no cloud fallback

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

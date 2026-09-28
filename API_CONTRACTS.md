# API and Data Contracts

## Create task

```http
POST /api/v1/tasks
```

Request:

```json
{
  "instruction": "Analyze the inspection report and prepare an approval note.",
  "attachment_ids": ["file_123"]
}
```

Response:

```json
{
  "task_id": "task_123",
  "status": "queued"
}
```

## Task events

```http
GET /api/v1/tasks/{task_id}/events
```

Event types:

```text
task_started
plan_created
model_selected
agent_started
tool_started
tool_completed
tool_failed
approval_required
approval_received
replan
verification_started
artifact_created
artifact_verified
task_completed
task_failed
```

## Approval

```http
POST /api/v1/tasks/{task_id}/approval
```

```json
{
  "decision": "approve",
  "comment": "Approved for draft generation."
}
```

## Evidence

```http
GET /api/v1/tasks/{task_id}/evidence
```

## Artifacts

```http
GET /api/v1/tasks/{task_id}/artifacts
```

## Sovereign status

```http
GET /api/v1/system/sovereign-status
```

Example:

```json
{
  "sovereign_mode": true,
  "external_connections_successful": 0,
  "blocked_egress_attempts": 0,
  "active_model_profile": "small"
}
```

## Model selection

Internal contract:

```python
resolve_model(
    capabilities: list[str],
    modalities: list[str],
    risk: str,
    context_tokens: int,
    tool_calling: bool,
) -> ModelSelection
```

The UI may display the result, but agent implementations should not depend on the UI.

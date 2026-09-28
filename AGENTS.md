# Agent Architecture

Agents are logical specialists. They do not own model selection.

## Main Agent

Responsibilities:
- accept task
- maintain workflow state
- invoke planning
- delegate
- aggregate results
- trigger verification
- deliver artifacts

## Reasoning Agent

Capabilities:
- planning
- decomposition
- synthesis
- structured reasoning

## Document Agent

Capabilities:
- PDF/DOCX ingestion
- page extraction
- document structure
- evidence normalization

## Vision Agent

Capabilities:
- image understanding
- scanned page analysis
- engineering drawing observations
- visual evidence

## Knowledge Agent

Capabilities:
- retrieve organizational knowledge
- hybrid search
- evidence ranking
- citation generation

## Coding Agent

Capabilities:
- read/write task files
- generate code
- execute tests in sandbox
- inspect failures
- repair code

## Data Agent

Capabilities:
- read CSV/XLSX
- perform calculations
- generate tables
- produce calculation traces

## Agent contract

Every agent must declare:

```yaml
agent_id:
description:
capabilities:
accepted_inputs:
produced_outputs:
allowed_tools:
risk_class:
max_retries:
```

## Delegation rule

Delegation must be capability-based:

```text
"Need visual reasoning"
```

not:

```text
"Call vision_agent because PDFs use vision_agent"
```

## Agent-to-agent communication

Use a structured A2A message:

```json
{
  "message_id": "...",
  "task_id": "...",
  "sender": "document_agent",
  "receiver": "knowledge_agent",
  "type": "REQUEST",
  "payload": {},
  "provenance": {}
}
```

## No hidden side effects

An agent cannot:
- access arbitrary host files
- make external HTTP requests
- call an unregistered tool
- modify persistent knowledge without an explicit operation
- execute code outside the sandbox

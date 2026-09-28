# Phase 3 Implementation Report — Registries, State & A2A Messaging

## Executive Summary
Phase 3 of the Sovereign On-Premise Agentic AI Workbench establishes the foundational discovery, state management, and communication infrastructure required by the future Phase 4 orchestrator. All components operate strictly locally under the permanent zero-egress air-gap policy (`SOVEREIGN_MODE=True`).

---

## 1. Authoritative Registries

The workbench establishes three authoritative registries without duplication:

### 1.1 Model Registry (`backend/app/models/registry.py`)
- **Profile Support**: Loads both `small` and `high` model configurations from YAML (`configs/models.small.yaml`, `configs/models.high.yaml`).
- **Dynamic Registration**: Supports `register()`, `unregister()`, `get()`, `get_or_raise()`, `list()`, and `exists()`.
- **Duplicate & Error Handling**: Raises `DuplicateModelError` when registering an existing model without `overwrite=True`, and `UnknownModelError` when querying non-existent models.
- **Capability & Modality Discovery**:
  - `find_by_capability(capability: str)`: Discovers models advertising capabilities (e.g., `reasoning`, `coding`, `vision`).
  - `find_by_modality(modality: str)`: Discovers models accepting specific input modalities (e.g., `text`, `image`).
  - `find_candidate_models()` & `resolve()`: Resolves models with fallback to active profile's general reasoning model.

### 1.2 Agent Registry (`backend/app/agents/registry.py`)
- **Pre-Populated Standard Agents**: Instantiates all 7 standard agents specified in `AGENTS.md`:
  1. `main_agent`: Workflow coordination, planning, delegation, aggregation, verification trigger, artifact delivery.
  2. `reasoning_agent`: Structured reasoning, planning, decomposition, synthesis.
  3. `document_agent`: PDF/DOCX ingestion, page extraction, document structure, evidence normalization.
  4. `vision_agent`: Image understanding, scanned page analysis, engineering drawings, visual reasoning.
  5. `knowledge_agent`: Local hybrid search, evidence ranking, citation generation.
  6. `coding_agent`: Task file I/O, code generation, sandbox test execution, repair loop.
  7. `data_agent`: Tabular data processing, calculation execution, spreadsheet/document generation.
- **Contract Enforcement**: Enforces `AgentContract` schema including risk classes and retries.
- **Discovery**:
  - `find_by_capability(capability: str)`: Discovers agents by capability.
  - `find_by_tool(tool_id: str)`: Discovers agents permitted to call a given tool.
- **Error Handling**: Raises `DuplicateAgentError` and `UnknownAgentError`.

### 1.3 Tool Registry (`backend/app/tools/registry.py`)
- **Pre-Populated Standard Tools**: Pre-registers the 8 core architecture tools:
  1. `file_read` (Risk: `LOW`, requires approval: `False`)
  2. `file_write` (Risk: `MEDIUM`, requires approval: `False`)
  3. `ocr` (Risk: `LOW`, requires approval: `False`)
  4. `knowledge_search` (Risk: `LOW`, requires approval: `False`)
  5. `python_calculation` (Risk: `MEDIUM`, requires approval: `False`)
  6. `sandbox_execute` (Risk: `HIGH`, requires approval: `True`)
  7. `create_docx` (Risk: `LOW`, requires approval: `False`)
  8. `create_xlsx` (Risk: `LOW`, requires approval: `False`)
- **Contract Enforcement**: Enforces `ToolContract` schema, input/output schemas, and risk levels.
- **Discovery**: `find_by_capability()`, `find_by_risk()`.
- **Error Handling**: Raises `DuplicateToolError` and `UnknownToolError`.

### 1.4 Diagnostic Snapshot (`backend/app/schemas/snapshot.py`)
- `get_registry_snapshot(model_registry, agent_registry, tool_registry) -> RegistrySnapshot`: Instantaneous diagnostic overview aggregating active counts, IDs, capabilities, and sovereignty status.

---

## 2. State Management Layer (`backend/app/state/`)

### 2.1 Task State Machine (`backend/app/state/task_state.py`)
- **Statuses (`TaskStatus`)**:
  `CREATED`, `UNDERSTANDING`, `PLANNING`, `WAITING_APPROVAL`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Strict Legal Transition Matrix**:
  - `CREATED` -> `UNDERSTANDING`, `CANCELLED`, `FAILED`
  - `UNDERSTANDING` -> `PLANNING`, `CANCELLED`, `FAILED`
  - `PLANNING` -> `WAITING_APPROVAL`, `EXECUTING`, `CANCELLED`, `FAILED`
  - `WAITING_APPROVAL` -> `EXECUTING`, `PLANNING`, `CANCELLED`, `FAILED`
  - `EXECUTING` -> `VERIFYING`, `CANCELLED`, `FAILED`
  - `VERIFYING` -> `COMPLETED`, `PLANNING`, `CANCELLED`, `FAILED`
  - Terminal states (`COMPLETED`, `FAILED`, `CANCELLED`): No further transitions permitted.
- **Fail-Closed Validation**: Any illegal transition raises `InvalidStateTransitionError`.
- **Audit Logging**: Every status transition automatically appends a `TASK_STATUS_CHANGED` event recording previous status, new status, and reason.

### 2.2 Execution Steps (`backend/app/state/execution_step.py`)
- **Step Lifecycle (`StepStatus`)**: `PENDING` -> `RUNNING` -> `COMPLETED` / `FAILED` / `SKIPPED`.
- Methods: `start()`, `complete(outputs)`, `fail(error)`, `skip(reason)`.
- Tracks timestamps, inputs, outputs, errors, and retry counts.

### 2.3 Comprehensive Event Logging (`backend/app/state/events.py`)
- 16 standard lifecycle audit event types (`EventType`):
  `TASK_CREATED`, `TASK_STATUS_CHANGED`, `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`, `STEP_SKIPPED`, `AGENT_DELEGATED`, `TOOL_CALLED`, `TOOL_COMPLETED`, `TOOL_FAILED`, `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `APPROVAL_REJECTED`, `VERIFICATION_STARTED`, `VERIFICATION_COMPLETED`, `TASK_ERROR`.
- Every event records `event_id`, `task_id`, `timestamp`, `agent_id`, `step_id`, `payload`, and `message`.

### 2.4 Crash-Resilient Persistence (`backend/app/state/store.py`)
- `LocalStateStore(StateStore)`:
  - Atomic File Writes: Writes to a unique `.tmp` file in the tasks directory, calls `flush()` and `os.fsync()`, then atomically swaps with `os.replace()`. Prevents file corruption upon power loss or abrupt termination.
  - JSONL Event Mirroring: Mirrors task events into an append-only `.jsonl` audit log.
  - Process Restart Recovery: Successfully recovers full state, steps, and audit logs when restarted.

---

## 3. Structured Agent-to-Agent (A2A) Messaging (`backend/app/agents/a2a.py`)

- **Message Schema (`A2AMessage`)**: Adheres to `AGENTS.md` message contract:
  - `message_id`, `task_id`, `sender`, `receiver`, `type`, `correlation_id`, `payload`, `provenance`, `requested_capabilities`, `status`.
- **A2A Message Types**:
  `REQUEST`, `RESPONSE`, `DELEGATION`, `NOTIFICATION`, `TASK_DELEGATION`, `TASK_RESULT`, `INFORMATION_REQUEST`, `INFORMATION_RESPONSE`, `TOOL_REQUEST`, `TOOL_RESULT`, `ERROR`, `STATUS_UPDATE`.
- **Strict Validation Rules**:
  - Rejects empty IDs.
  - Rejects self-messaging (`sender == receiver`).
  - Rejects unknown or disabled agents when validated against `AgentRegistry`.
  - **Capability-Based Delegation Rule (`AGENTS.md`)**: Rejects delegation if the recipient agent lacks the requested capabilities (e.g. delegating `visual_reasoning` to `data_agent` fails closed).
- **Offline In-Memory Processing**: No external HTTP or socket requests are made during message creation or validation.

---

## 4. Verification and Test Results

The full test suite across Phase 0, Phase 1, Phase 2, and Phase 3 runs cleanly:
- Total tests executed: **142**
- Tests passed: **141**
- Tests skipped: **1** (live hardware endpoint test skipped cleanly when external vLLM is not running)
- Tests failed: **0**

### Acceptance Criteria Matrix (17 / 17 passed)
| Acceptance Criterion | Description | Result |
| :--- | :--- | :---: |
| Acceptance 1 | Phase 0 settings & contracts valid | **PASS** |
| Acceptance 2 | Phase 1 model runtime construction & registry resolution | **PASS** |
| Acceptance 3 | Phase 2 sovereignty policy & zero-egress enforcement | **PASS** |
| Acceptance 4 | ModelRegistry dynamic registration, duplicate checks, capability discovery | **PASS** |
| Acceptance 5 | AgentRegistry 7 standard agents & capability discovery | **PASS** |
| Acceptance 6 | ToolRegistry 8 standard tools & risk-level filtering | **PASS** |
| Acceptance 7 | TaskState initialization & non-terminal defaults | **PASS** |
| Acceptance 8 | Legal state transitions along lifecycle paths | **PASS** |
| Acceptance 9 | Illegal state transitions fail closed with InvalidStateTransitionError | **PASS** |
| Acceptance 10 | Terminal states (COMPLETED, FAILED, CANCELLED) block further transitions | **PASS** |
| Acceptance 11 | ExecutionStep lifecycle (PENDING -> RUNNING -> COMPLETED) | **PASS** |
| Acceptance 12 | Comprehensive 16-event lifecycle logging | **PASS** |
| Acceptance 13 | Structured A2A message contract and self-messaging rejection | **PASS** |
| Acceptance 14 | A2A capability-based delegation rule verification | **PASS** |
| Acceptance 15 | LocalStateStore crash resilience & state persistence | **PASS** |
| Acceptance 16 | StateStore atomic writes and clean temporary file cleanup | **PASS** |
| Acceptance 17 | Registries, StateStore, and A2A operate with zero network egress | **PASS** |

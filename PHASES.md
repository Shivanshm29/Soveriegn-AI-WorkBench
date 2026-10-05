# Implementation Phases

Each phase has a concrete exit gate. Do not move to the next phase until the gate passes.

## Phase 0 — Architecture and configuration contract

### Build
- `USE_HIGH_LEVEL_MODELS=false` as default.
- Settings loader.
- Model profile schema.
- Model registry schema.
- Agent/tool capability schemas.

### Exit gate
Changing only the environment variable changes the active model profile without changing agent code.

---

## Phase 1 — Local model runtime

### Build
- OpenAI-compatible local runtime adapter.
- vLLM adapter.
- Optional Transformers fallback.
- Health checks.
- Model lifecycle manager.
- VRAM availability probe.

### Exit gate
A local general model answers through the application API with no external API.

---

## Phase 2 — Sovereign boundary

### Build
- Docker network isolation for sandbox.
- Local-only runtime configuration.
- Outbound connection policy.
- Egress event collector.
- Visible sovereign status.

### Exit gate
A test suite proves normal tasks create zero successful external connections.

---

## Phase 3 — Registries and state

### Build
- AgentRegistry.
- ToolRegistry.
- ModelRegistry.
- Task/session isolation.
- Structured state object.
- Audit event schema.

### Exit gate
An unauthorized agent/tool combination is rejected before execution.

---

## Phase 4 — LangGraph orchestration

### Build
- understand node
- risk node
- route node
- plan node
- policy node
- approval interrupt
- execution node
- observation node
- replanning node
- verification node
- delivery node

### Exit gate
A synthetic multi-step task produces a visible plan and can recover from one failed tool call.

---

## Phase 5 — Risk and approval

### Build
Risk classes:
- LOW
- MEDIUM
- HIGH
- CRITICAL

Policy decides whether approval is required.

### Exit gate
A high-risk artifact action pauses execution and resumes only after explicit approval.

---

## Phase 6 — Multimodal document pipeline

### Build
- PDF classification
- text extraction
- page rendering
- OCR
- bounding boxes
- tables
- images
- VLM reasoning
- normalized evidence objects

### Exit gate
A scanned PDF produces page-level evidence with OCR confidence and source coordinates.

---

## Phase 7 — Vision / engineering drawing workflow

### Build
- image understanding
- text/tag extraction
- region references
- spatial observations
- confidence
- human-review flag

### Exit gate
An engineering drawing can be analyzed without converting it into text only.

---

## Phase 8 — Local RAG

### Build
- ingestion
- parsing
- structure-aware chunking
- embeddings
- Qdrant
- BM25
- RRF
- metadata filters
- source citations

### Exit gate
A known answer is retrieved with correct source document and page metadata.

---

## Phase 9 — Coding agent

### Build
- repository/file read
- code generation
- sandbox execution
- test execution
- failure observation
- repair/retry

### Exit gate
A deliberately broken generated program is repaired after an actual sandbox failure.

---

## Phase 10 — Data/calculation agent

### Build
- CSV/XLSX reader
- Python calculations
- formula trace
- units
- result provenance

### Exit gate
The numerical result comes from an executed tool, not model-generated arithmetic.

---

## Phase 11 — Artifact factory

### Build
- DOCX
- XLSX
- CSV
- code bundles
- reports

### Exit gate
Generated artifacts are reopened and structurally verified before delivery.

---

## Phase 12 — Provenance graph

### Build
Link:

```text
final output
→ claim
→ calculation/retrieval
→ source
→ page
→ region
→ model/tool
→ task
```

### Exit gate
A reviewer can click from a generated claim to its source evidence.

---

## Phase 13 — Evaluation and red-team

### Build
- task completion metrics
- retrieval metrics
- OCR metrics
- artifact verification metrics
- sandbox security tests
- prompt-injection tests
- egress tests

### Exit gate
All mandatory acceptance tests are automated.

---

## Phase 14 — End-to-end demonstration build

### Demo A
Scanned inspection report → SOP retrieval → approval note DOCX.

### Demo B
Coding request → sandbox → failure → repair → verified output.

### Demo C
Engineering drawing → OCR/VLM → knowledge lookup → evidence-backed response.

### Exit gate
All three demos work on the small profile with `USE_HIGH_LEVEL_MODELS=false`.

# Antigravity Master Implementation Prompt

You are implementing the **Sovereign On-Premise Agentic AI Workbench** for SIH 2026 Problem Statement 26117.

## Source of truth

Read these project documents before changing code:

1. `README.md`
2. `PROJECT_SCOPE.md`
3. `ARCHITECTURE.md`
4. `PHASES.md`
5. `MODELS.md`
6. `MODEL_ROUTING.md`
7. `AGENTS.md`
8. `MULTIMODAL.md`
9. `RAG.md`
10. `SECURITY.md`
11. `SANDBOX.md`
12. `ARTIFACTS.md`
13. `PROVENANCE.md`
14. `EVALUATION.md`
15. `CONFIGURATION.md`
16. `API_CONTRACTS.md`
17. `DEMO_PLAN.md`
18. `ACCEPTANCE_MATRIX.md`

## Non-negotiable requirements

### 1. Small models first

Default:

```env
USE_HIGH_LEVEL_MODELS=false
```

Implement the small profile first:

```text
Qwen/Qwen3-4B
Qwen/Qwen3-VL-4B-Instruct
Qwen/Qwen2.5-Coder-3B-Instruct
```

Do not require the high models for development.

### 2. High-model toggle

When:

```env
USE_HIGH_LEVEL_MODELS=true
```

resolve:

```text
Qwen/Qwen3-30B-A3B
Qwen/Qwen3-VL-30B-A3B-Instruct
Qwen/Qwen3-Coder-30B-A3B-Instruct
```

The agent code must not change.

### 3. No hard-coded agent/model mapping

Agents request capabilities.

The Model Router decides the model.

### 4. Sovereignty

Normal operation must not require:
- cloud LLM APIs
- cloud OCR
- web search
- external telemetry

Do not add a "temporary" cloud fallback.

### 5. LangGraph

Use LangGraph for:
- state
- planning
- delegation
- approval interrupts
- retries
- replanning
- verification
- delivery

Do not implement the main agent as a single giant while-loop.

### 6. Real tools

Implement registered tools for:
- file read
- file write
- OCR
- knowledge search
- Python calculation
- sandbox execution
- DOCX generation
- XLSX generation

### 7. Security

All code execution is sandboxed.

All external content is untrusted data.

All high-risk actions pass through policy.

### 8. Evidence

Do not generate unsupported claims as if they were verified facts.

Every knowledge-backed claim should retain source metadata.

### 9. Artifacts

Deliver real files and verify them before claiming success.

### 10. Observability

Every important action emits a structured event.

## Implementation discipline

Work phase-by-phase according to `PHASES.md`.

After each phase:
1. implement
2. write tests
3. run tests
4. fix failures
5. update acceptance status
6. only then proceed

Do not create placeholder functions that return fake success.

If a dependency is unavailable, report it and provide a local fallback rather than silently changing the architecture.

## Initial priority order

```text
P0
P1
P2
P3
P4
P5
P6
P8
P9
P10
P11
P12
P13
P14
```

P7 vision can be developed alongside P6 after the document pipeline works.

## Initial repository target

```text
backend/
  app/
    api/
    agents/
    orchestration/
    models/
    tools/
    security/
    rag/
    multimodal/
    artifacts/
    provenance/
    audit/
    config/
    schemas/
    services/
    tests/

frontend/
  app/
  components/
  lib/

configs/
  models.small.yaml
  models.high.yaml
  policies.yaml

docs/
  ...

data/
  attachments/
  knowledge/
  artifacts/
  audit/

sandbox/
  ...

tests/
  acceptance/
  security/
  integration/
```

## Model registry implementation

Create a `ModelProfile` schema and registry.

Do not import model-specific logic into agents.

Use an adapter:

```python
class ModelRuntime(Protocol):
    def chat(...): ...
    def health(...): ...
    def capabilities(...): ...
```

Then:

```text
ModelRouter
   ↓
ModelRuntime
   ↓
local runtime
```

## Router behavior

Use deterministic, explainable scoring initially.

The router must produce:
- selected model
- candidate models
- score
- reasons
- hardware snapshot
- active profile

## Important hardware behavior

If the high model does not fit:
- do not OOM the host
- do not silently switch to cloud
- return a clear local-capability error or select a compatible registered local model

## Final success condition

The system must be able to run this on the small profile:

> Read a scanned inspection report, extract findings, retrieve the relevant local SOP, draft an approval note, require human approval, create a DOCX, verify it, and show evidence plus zero-egress telemetry.

And this:

> Generate code, run it in a no-network sandbox, observe a real failure, repair it, rerun it, and deliver the verified result.

And this:

> Analyze an engineering drawing with OCR/VLM and cross-reference local knowledge with source evidence.

Do not optimize for a large feature count. Optimize for a small number of real, testable end-to-end workflows.

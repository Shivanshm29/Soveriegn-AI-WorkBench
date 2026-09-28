# Architecture Decisions

## ADR-001 — Capability-based model routing

**Decision:** Agents request capabilities; the Model Router selects the model.

**Reason:** Allows new local models to be added without rewriting agents.

---

## ADR-002 — Small models are the default

**Decision:** `USE_HIGH_LEVEL_MODELS=false` by default.

**Reason:** The venue/demo system must be runnable without server-class hardware.

---

## ADR-003 — Separate vision and coding models

**Decision:** Use specialist models rather than forcing one small general model to perform every modality.

**Reason:** The problem explicitly requires multimodal work and coding.

---

## ADR-004 — OCR is a separate subsystem

**Decision:** Use local OCR plus VLM reasoning.

**Reason:** OCR output needs coordinates/confidence and visual reasoning needs image context.

---

## ADR-005 — LangGraph for orchestration

**Decision:** The main agent is a stateful graph.

**Reason:** Planning, approval, retry, resume and replanning are first-class workflow operations.

---

## ADR-006 — No cloud fallback

**Decision:** Sovereign mode never falls back to external AI.

**Reason:** Confidentiality is a core system requirement, not an optimization.

---

## ADR-007 — Persistent KB is explicit

**Decision:** Attachments and persistent knowledge are separate.

**Reason:** Users must not accidentally turn a confidential task artifact into long-lived organizational memory.

---

## ADR-008 — Artifact verification is mandatory

**Decision:** A generated file is not considered successful until it is reopened/validated.

**Reason:** File generation failures can otherwise be hidden behind plausible chat text.

---

## ADR-009 — Provenance is a first-class object

**Decision:** Evidence is stored independently of the final response.

**Reason:** Auditing and human review require traceability beyond citations embedded in prose.

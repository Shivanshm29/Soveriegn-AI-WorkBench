# Sovereign On-Premise Agentic AI Workbench

**Enterprise Confidential & Air-Gapped Industrial AI**

A model-agnostic, self-hosted, multimodal agentic AI workbench for confidential industrial knowledge work.

## Core principle

> **Nothing leaves the organization's controlled environment.**

The system is designed around:

**UNDERSTAND → ROUTE → PLAN → APPROVE → EXECUTE → VERIFY → DELIVER**

The implementation must remain useful on a modest local GPU while allowing the same architecture to switch to larger local models later.

## The one model-profile toggle

The authoritative environment switch is:

```env
USE_HIGH_LEVEL_MODELS=false
```

- `false` → **SMALL profile**: Qwen3-4B, Qwen3-VL-4B-Instruct, Qwen2.5-Coder-3B-Instruct.
- `true` → **HIGH profile**: Qwen3-30B-A3B, Qwen3-VL-30B-A3B-Instruct, Qwen3-Coder-30B-A3B-Instruct.

Agents must never hard-code model names. They request capabilities; the Model Router resolves the actual model from the active profile and runtime availability.

## Initial technology direction

- **Backend:** Python + FastAPI
- **Workflow:** LangGraph
- **Model serving:** vLLM where supported; local Transformers/llama.cpp fallback when appropriate
- **OCR:** PaddleOCR
- **Vision:** Qwen3-VL
- **General reasoning:** Qwen3
- **Coding:** Qwen2.5-Coder / Qwen3-Coder
- **RAG:** Qdrant + dense retrieval + BM25 + RRF
- **Embeddings:** EmbeddingGemma or another locally registered embedding model
- **Sandbox:** Docker, network disabled
- **Artifacts:** python-docx, openpyxl, reportlab, standard local file APIs
- **Frontend:** Next.js/React
- **Persistence:** PostgreSQL for metadata/audit; filesystem/object-store-compatible local storage for artifacts
- **Observability:** structured audit events + local network/egress telemetry

## What makes this different

1. Capability-based adaptive model routing.
2. Hardware-aware model selection and optional model hot-swapping.
3. Multimodal evidence pipeline: OCR + layout + tables + images + VLM.
4. Risk-adaptive human approval.
5. Agentic retry/replan after real tool failures.
6. Evidence/provenance graph from final output back to source page/region.
7. Verified deliverables instead of chat-only answers.
8. Machine-verifiable zero-egress mode.
9. Persistent organizational knowledge is explicitly separated from transient task attachments.
10. New local models can be registered without changing agent implementations.

## Source basis

The workbench architecture defines the sovereign workflow `UNDERSTAND → ROUTE → PLAN → APPROVE → EXECUTE → VERIFY → DELIVER`, adaptive model routing, multimodal document processing, policy/human approval, agent execution, and traceability.

The project documents in this folder turn that architecture into concrete implementation contracts and acceptance gates.

# Initial Build Checklist

## Foundation
- [x] repository structure
- [x] settings loader
- [x] `.env.example`
- [x] small/high model profiles
- [x] model registry
- [x] agent registry
- [x] tool registry

## Runtime
- [x] local model health check
- [x] vLLM adapter
- [ ] optional Transformers fallback
- [x] hardware probe
- [x] model lifecycle manager

## Sovereignty
- [x] outbound policy
- [ ] sandbox network isolation
- [x] egress telemetry
- [x] sovereign status endpoint

## Registries, State & A2A (Phase 3)
- [x] dynamic ModelRegistry with capability & modality lookup
- [x] pre-populated AgentRegistry with 7 standard agents
- [x] pre-populated ToolRegistry with 8 standard tools
- [x] diagnostic RegistrySnapshot aggregator
- [x] TaskState and legal transition state machine
- [x] ExecutionStep lifecycle (PENDING -> RUNNING -> COMPLETED/FAILED/SKIPPED)
- [x] 16 standard TaskEvent lifecycle audit types
- [x] LocalStateStore with atomic crash-resilient persistence
- [x] structured A2AMessage contract & capability validation


## Agent (Phase 4 Orchestration)
- [x] LangGraph state
- [x] planner
- [x] router
- [x] policy gate (Phase 4 integration checkpoint)
- [x] approval interrupt (Phase 5)
- [x] execution
- [x] observation
- [x] replanning
- [x] verification
- [x] delivery

## Risk, Policy & Approval (Phase 5)
- [x] local policy engine & configs/policies.yaml
- [x] deterministic risk scoring & factor analysis (LOW, MEDIUM, HIGH, CRITICAL)
- [x] data sensitivity classification (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)
- [x] tool risk metadata integration from ToolRegistry
- [x] human approval model (ApprovalRequest, ApprovalDecision, statuses)
- [x] approval scope binding & plan hash validation
- [x] approval expiration & immutability
- [x] WAITING_APPROVAL state & LangGraph conditional interrupt/resume
- [x] fail-closed enforcement (unknown tools, unknown agents, invalid/expired approvals)
- [x] zero-egress sovereignty non-bypassability
- [x] policy versioning & lifecycle audit events

## Multimodal (Phase 6)
- [x] PDF parser (PyMuPDF local extraction)
- [x] page rendering (local rasterization)
- [x] local OCR & coordinates normalization
- [x] layout & table analysis
- [x] evidence object & prompt injection defense
- [x] Qwen3-VL adapter (dynamic ModelRegistry/ModelRuntime resolution)

## RAG
- [ ] ingestion
- [ ] embeddings
- [ ] Qdrant
- [ ] BM25
- [ ] RRF
- [ ] citations
- [ ] injection defense

## Coding
- [ ] sandbox
- [ ] tests
- [ ] repair loop

## Artifacts
- [ ] DOCX
- [ ] XLSX
- [ ] CSV
- [ ] artifact verification

## Trust
- [ ] provenance
- [ ] audit log
- [ ] evaluation suite
- [ ] red-team suite

## Demo
- [ ] inspection report
- [ ] coding failure/repair
- [ ] engineering drawing
- [ ] zero-egress proof

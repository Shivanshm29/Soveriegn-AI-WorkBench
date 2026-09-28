# Acceptance Matrix

| ID | Requirement | Acceptance test |
|---|---|---|
| A01 | Small profile default | Fresh setup runs with `USE_HIGH_LEVEL_MODELS=false` |
| A02 | High profile toggle | Changing only env toggle selects high profile |
| A03 | Model agnostic | Agents contain no hard-coded model IDs |
| A04 | Adaptive routing | Same task produces a capability-based routing decision |
| A05 | Hardware awareness | Router rejects a model over configured hardware budget |
| A06 | Local runtime | Model call resolves to configured local endpoint |
| A07 | Zero egress | Test suite reports no successful external calls |
| A08 | Tool authorization | Unauthorized tool call is rejected |
| A09 | Task isolation | Task A cannot read Task B files |
| A10 | LangGraph | Multi-step task is represented by persisted graph state |
| A11 | Replanning | Failed tool execution causes a recovery path |
| A12 | Approval | High-risk action pauses before execution |
| A13 | OCR | Scanned page produces OCR text and coordinates |
| A14 | Vision | Image-dependent task uses a vision-capable model |
| A15 | RAG | Retrieval returns source metadata |
| A16 | Hybrid retrieval | Dense + lexical retrieval are fused |
| A17 | Prompt injection | Malicious document text cannot alter system policy |
| A18 | Sandbox | Code runs without network access |
| A19 | Sandbox repair | Agent fixes a real execution failure |
| A20 | Calculation | Numeric result comes from executed calculation |
| A21 | DOCX | DOCX is generated and reopened for validation |
| A22 | XLSX | XLSX is generated and reopened for validation |
| A23 | Provenance | Final claim links to source evidence |
| A24 | Audit | Key events are persisted |
| A25 | Demo 1 | Inspection report → verified approval note works |
| A26 | Demo 2 | Coding → sandbox → repair → verified result works |
| A27 | Demo 3 | Drawing → vision → RAG → evidence works |

## Release rule

The SIH demo release requires A01–A27 to pass or have an explicitly documented hardware-dependent exception.

# Project Scope

## Problem

Sensitive industrial knowledge work includes approval notes, board presentations, engineering calculations, internal code, scanned inspection reports, drawings, vendor material, financial information and internal correspondence. The workbench must support this work without requiring confidential inputs to leave the controlled environment.

## In scope

### Inputs
- Text
- Images
- PDFs
- Scanned PDFs
- DOCX
- XLSX/CSV
- Source code
- Engineering drawings/images

### Core capabilities
- Task understanding
- Risk classification
- Adaptive local model routing
- Multi-step planning
- Human approval for policy-defined actions
- Local tool use
- OCR and visual understanding
- Local knowledge retrieval
- Sandboxed code execution
- Calculation execution
- Artifact generation
- Artifact verification
- Evidence and provenance
- Audit logging
- Egress monitoring

### Initial end-to-end workflows
1. Scanned inspection report → findings → SOP retrieval → approval note DOCX.
2. Coding request → code generation → sandbox test → repair → verified result.
3. Engineering drawing → OCR/VLM extraction → knowledge lookup → evidence-backed response.

## Out of scope for the initial implementation

- Training foundation models from scratch.
- Automatic irreversible enterprise actions.
- Autonomous approval of high-risk actions.
- Cloud model fallback.
- External web search during normal sovereign operation.
- Automatic ingestion of every uploaded file into persistent organizational memory.
- Claims that an AI interpretation is an engineering certification.

## Design rule

If a feature is not required to demonstrate the three core workflows or the sovereign claim, it should not block the first demonstrable release.

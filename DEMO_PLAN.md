# SIH Local Demonstration Plan

This document provides the exact commands, execution steps, and verification outputs to reproduce the 5 core demonstrations of the **Sovereign On-Premise Agentic AI Workbench** locally.

---

## Prerequisites & Sovereign Environment Setup

Ensure you are in the project root directory with Python dependencies installed:

```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -v
```

All operations run 100% on-premise with zero external network egress.

---

## DEMO 1: Scanned Inspection Report → Local OCR/Vision → Findings → DOCX Approval Note

### Objective
Demonstrate automated ingestion of an industrial inspection report, local visual defect observation, deterministic evidence normalization, policy verification, and creation of a verified Word (`.docx`) approval note citing visual evidence.

### Command to Execute
```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -k "test_sih_demo_scenario_1" -v -s
```

### Key Workflow Steps
1. User submits an industrial equipment scan (`flange_inspection.png`).
2. Security gate validates input path (rejects path traversal).
3. `TaskUnderstanding` routes request to `vision_agent` and `document_agent`.
4. `vision_agent` detects candidate anomalies and extracts spatial evidence regions.
5. Findings are framed strictly as candidate observations requiring qualified NDT verification.
6. `document_agent` creates an auditable `.docx` approval note citing specific evidence IDs.
7. `ArtifactVerifier` checks file readability, SHA-256 hash, and verifies that citations match actual evidence.

---

## DEMO 2: Coding Task → High-Risk Policy Gate → Human Approval → Sandbox Execution → Network Blocked

### Objective
Demonstrate local code generation, policy enforcement on high-risk tools, interactive human approval pause/resume, sandboxed execution with verified network blockage, and deterministic verification.

### Command to Execute
```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -k "test_sih_demo_scenario_2" -v -s
```

### Key Workflow Steps
1. User requests: *"Write a Python script to calculate statistics from this CSV and execute in the sandbox."*
2. `CodingAgent` dynamically resolves the coding model (`Qwen2.5-Coder-3B-Instruct` or `Qwen3-Coder-30B-A3B-Instruct`) through `ModelRegistry`.
3. Plan includes `sandbox_execute` (classified as `HIGH` risk).
4. `PolicyEngine` pauses the workflow in `WAITING_APPROVAL` status and generates a cryptographically bound `ApprovalRequest`.
5. Human supervisor approves the request with matching `plan_hash`.
6. Orchestrator resumes execution into `LocalProcessSandbox` / `DockerSandbox`.
7. Subprocess attempts network access (`urllib.request.urlopen`); network access is intercepted and blocked:
   ```
   NETWORK ACCESS BLOCKED: Sandbox network is disabled.
   ```
8. Execution completes successfully (code 0) within resource limits.

---

## DEMO 3: Confidential Knowledge Query → Hybrid RAG → Evidence Pack → Citations

### Objective
Demonstrate local hybrid retrieval (Qdrant dense vector search + BM25 lexical ranking + Reciprocal Rank Fusion) and grounded question answering with zero data leakage to cloud endpoints.

### Command to Execute
```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -k "test_sih_demo_scenario_3" -v -s
```

### Key Workflow Steps
1. Document `PX417_SOP.txt` is ingested locally with sensitivity `CONFIDENTIAL`.
2. User submits query: *"What does the maintenance procedure recommend for pump PX-417 vibration?"*
3. `KnowledgeAgent` enforces sensitivity access control.
4. Hybrid search retrieves relevant chunks without network calls.
5. Structured `EvidencePack` is passed to the local LLM.
6. Model returns a grounded answer with explicit citations to `PX417_SOP.txt`.
7. `RAGVerifier` validates citation authenticity against the evidence pack.

---

## DEMO 4: Industrial Engineering Image → Candidate Defect Indication

### Objective
Demonstrate visual reasoning on industrial components while preventing model hallucination of certified engineering conclusions.

### Command to Execute
```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -k "test_sih_demo_scenario_4" -v -s
```

### Key Workflow Steps
1. Industrial equipment photograph is ingested.
2. `EngineeringVisionAgent` analyzes visual regions and identifies surface indications.
3. Every observation flags `candidate_observation = True` and `verification_required = True`.
4. Output explicitly states that physical non-destructive testing (NDT) is required before certification.

---

## DEMO 5: Mixed Multi-Agent Industrial Workflow (Document + Vision + Knowledge + Data + Artifact)

### Objective
Demonstrate all logical specialists collaborating seamlessly within ONE single LangGraph state machine.

### Command to Execute
```bash
python -m pytest tests/acceptance/test_phase_9_acceptance.py -k "test_sih_demo_scenario_5" -v -s
```

### Key Workflow Steps
1. User query:
   ```
   "Analyze this inspection report, check the maintenance procedure for the equipment, calculate the reported measurements, and prepare an approval note."
   ```
2. State Graph coordinates 4 distinct specialists in sequence:
   - `vision_agent`: Analyzes report image and extracts visual regions.
   - `knowledge_agent`: Searches local knowledge base for equipment SOP.
   - `data_agent`: Deterministically calculates dataset statistics.
   - `document_agent`: Synthesizes all outputs into a verified `.docx` approval note.
3. `verify_node` verifies plan completion, output schemas, and file existence.
4. `deliver_node` finalizes the task as `COMPLETED`.

---

## Comprehensive Regression Verification Command

To run the complete verification across all phases (P0 to P9):

```bash
python -m pytest tests/acceptance -v
```

Expected result: **148 passed, 0 failed**.

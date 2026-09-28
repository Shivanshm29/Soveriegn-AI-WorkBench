# SIH Demonstration Plan

## Demo 1 — Inspection report to approval note

### Input
- scanned inspection report
- internal SOP

### Workflow

```text
UNDERSTAND
→ RISK
→ ROUTE
→ PLAN
→ OCR/VISION
→ KNOWLEDGE RETRIEVAL
→ FINDINGS
→ CALCULATION
→ HUMAN APPROVAL
→ DOCX
→ VERIFY
→ DELIVER
```

### Visible proof
- selected model and reason
- page-level evidence
- SOP citation
- approval gate
- generated DOCX
- artifact verification
- audit timeline
- zero-egress status

---

## Demo 2 — Coding agent

### Input

"Build a Python analyzer for this CSV and verify the result."

### Workflow

```text
PLAN
→ CODE
→ SANDBOX
→ TEST
→ FAILURE
→ REPLAN
→ REPAIR
→ TEST
→ VERIFY
→ DELIVER
```

### Visible proof
Show the actual failed execution followed by the repaired execution.

---

## Demo 3 — Engineering drawing

### Input
- engineering drawing image
- internal maintenance document

### Workflow

```text
IMAGE
→ OCR
→ VLM
→ TAG/REGION EXTRACTION
→ KNOWLEDGE SEARCH
→ CROSS-CHECK
→ EVIDENCE
```

### Visible proof
Click a finding and show the source region/page.

## Demo rule

Never fake:
- model selection
- tool execution
- calculation
- network status
- artifact verification

All displayed statuses must come from real runtime events.

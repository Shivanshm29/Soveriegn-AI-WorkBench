# Provenance and Evidence Graph

## Goal

A reviewer should be able to answer:

> "Where did this statement in the final deliverable come from?"

## Graph

```text
Artifact
  ↓
Claim
  ↓
Evidence
  ├── document/page/region
  ├── retrieval result
  └── calculation
        ↓
      tool run
        ↓
      input data
```

## Example

```text
Approval Note
  ↓
"Inspection finding X exceeds threshold"
  ↓
Calculation C-17
  ↓
Python execution E-44
  ↓
CSV row 381
```

and:

```text
Approval Note
  ↓
"Finding requires action under SOP-17"
  ↓
Knowledge evidence
  ↓
SOP-17.pdf
  ↓
page 12
  ↓
chunk KB-884
```

## Provenance requirements

Every important claim should retain:
- task_id
- source document
- page
- region where available
- retrieval method
- model/tool used
- timestamp
- source hash

## Why this matters

The provenance layer is not merely a citation feature. It is the bridge between:
- AI output
- enterprise evidence
- auditability
- human review

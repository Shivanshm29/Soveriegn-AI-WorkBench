# Evaluation and Red Team

## Evaluation categories

### 1. Agentic execution
Measure:
- task completion
- correct tool selection
- successful replanning
- retry success

### 2. RAG
Measure:
- Recall@K
- MRR
- citation correctness
- source/page correctness

### 3. Multimodal
Measure:
- OCR accuracy
- page detection
- table extraction
- visual evidence correctness
- region/provenance correctness

### 4. Coding
Measure:
- tests passed
- repair after failure
- sandbox policy violations
- execution timeout handling

### 5. Artifacts
Measure:
- generated
- opens successfully
- structural validation
- content validation

### 6. Security
Measure:
- unauthorized tool call rejection
- cross-task isolation
- prompt injection resistance
- external connection blocking

## Minimum test suite

```text
10 text tasks
10 RAG tasks
10 scanned-document tasks
10 visual tasks
10 coding tasks
5 calculation tasks
5 artifact tasks
5 prompt-injection tasks
5 sandbox escape tests
5 zero-egress tests
```

## Model profile comparison

Run the same benchmark with:

```text
USE_HIGH_LEVEL_MODELS=false
```

and:

```text
USE_HIGH_LEVEL_MODELS=true
```

Record:
- quality
- latency
- VRAM
- failures
- task completion

Do not encode a subjective "winner". Store measurable results.

## Acceptance philosophy

A feature is complete when a test proves it, not when the UI appears to support it.

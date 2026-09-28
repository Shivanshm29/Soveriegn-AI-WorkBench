# Adaptive Model Routing

## Objective

Select a local model based on task requirements rather than hard-coded agent-to-model mappings.

## Inputs to the router

```json
{
  "task_type": "document_analysis",
  "modalities": ["pdf", "image", "text"],
  "capabilities": [
    "ocr_assistance",
    "visual_reasoning",
    "document_reasoning"
  ],
  "risk": "high",
  "context_tokens": 18000,
  "requires_tools": true,
  "hardware": {
    "free_vram_gb": 7.4
  }
}
```

## Selection pipeline

```text
Task
 ↓
Capability extraction
 ↓
Candidate filtering
 ↓
Profile filter
 ↓
Modality compatibility
 ↓
Tool/structured-output compatibility
 ↓
Context compatibility
 ↓
Hardware fit
 ↓
Local health check
 ↓
Scoring
 ↓
Selected model
```

## Recommended scoring

Do not use a black-box learned router initially. Use an auditable deterministic scorer.

```text
score =
  capability_match * 0.35
+ modality_match   * 0.20
+ hardware_fit     * 0.15
+ context_fit      * 0.10
+ tool_support     * 0.10
+ latency_fit      * 0.05
+ health_status    * 0.05
```

The weights should live in configuration.

## Critical rule

The router must expose the reason for its decision.

Example:

```json
{
  "selected_model": "qwen3-vl-small",
  "reason": [
    "image modality required",
    "visual reasoning capability required",
    "context requirement satisfied",
    "available VRAM sufficient",
    "model is healthy"
  ]
}
```

## Model-profile toggle behavior

```text
USE_HIGH_LEVEL_MODELS=false
        ↓
active_profile = small

USE_HIGH_LEVEL_MODELS=true
        ↓
active_profile = high
```

The router can still choose among multiple models within the active profile.

## No silent downgrade

If no model satisfies a required capability, return:

```text
MODEL_CAPABILITY_UNAVAILABLE
```

Do not silently use an incompatible model.

## Model selection audit event

Store:

```json
{
  "event": "model_selected",
  "task_id": "...",
  "agent_id": "...",
  "requested_capabilities": [],
  "candidate_models": [],
  "selected_model": "...",
  "active_profile": "small",
  "reason": [],
  "hardware_snapshot": {}
}
```

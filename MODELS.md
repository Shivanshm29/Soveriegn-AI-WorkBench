# Model Strategy

## Important

The project is model-agnostic at the architecture level.

Model names in this document are **initial profiles**, not hard-coded dependencies.

The current verified model candidates are from the Qwen family because small and larger variants exist for general reasoning, vision and coding.

## Authoritative environment switch

```env
USE_HIGH_LEVEL_MODELS=false
```

### `false` — SMALL profile

| Capability | Model |
|---|---|
| General reasoning | `Qwen/Qwen3-4B` |
| Vision/document | `Qwen/Qwen3-VL-4B-Instruct` |
| Coding | `Qwen/Qwen2.5-Coder-3B-Instruct` |

These are deliberately small initial targets. The application should still support quantization and sequential loading.

### `true` — HIGH profile

| Capability | Model |
|---|---|
| General reasoning | `Qwen/Qwen3-30B-A3B` |
| Vision/document | `Qwen/Qwen3-VL-30B-A3B-Instruct` |
| Coding | `Qwen/Qwen3-Coder-30B-A3B-Instruct` |

The high profile is for a larger local GPU/server. It must never be required for development.

## Why separate models

### General reasoning
Used for:
- task understanding
- planning
- reasoning
- synthesis
- policy interpretation

### Vision-language
Used for:
- scanned pages
- images
- tables in page images
- drawings
- spatial observations
- visual evidence

### Coding
Used for:
- code generation
- code repair
- tests
- repository reasoning
- tool-oriented coding

## Model registry contract

Every model record must contain:

```yaml
id:
family:
profile:
capabilities:
input_modalities:
output_modalities:
context_length:
tool_calling:
structured_output:
quantization:
min_vram_gb:
preferred_runtime:
enabled:
```

## Fallback policy

If the selected model:
- is not installed,
- fails health checks,
- exceeds the hardware budget,

the router may select another **locally registered** model that satisfies the required capabilities.

It must never fall back to a cloud model.

## Important non-claim

The project must not claim that a small model is equivalent to a large model. The small profile is the runnable development/demo profile; the high profile is the higher-capability deployment option.

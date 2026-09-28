# Configuration

## Primary environment switch

```env
USE_HIGH_LEVEL_MODELS=false
```

This is the only switch required to move between the initial small and high model profiles.

## Example

```env
APP_ENV=development
SOVEREIGN_MODE=true
USE_HIGH_LEVEL_MODELS=false

MODEL_RUNTIME=vllm
MODEL_BASE_URL=http://127.0.0.1:8000/v1

GENERAL_MODEL=
VISION_MODEL=
CODING_MODEL=

MAX_CONTEXT_TOKENS=16384
MAX_AGENT_STEPS=20
MAX_RETRIES=2

GPU_MEMORY_UTILIZATION=0.85

RAG_ENABLED=true
OCR_ENABLED=true
SANDBOX_ENABLED=true

SANDBOX_CPU_LIMIT=2
SANDBOX_MEMORY_MB=2048
SANDBOX_TIMEOUT_SECONDS=20

DATABASE_URL=postgresql://localhost/sovereign_ai
QDRANT_URL=http://127.0.0.1:6333
```

## Resolution order

The application must resolve models in this order:

```text
USE_HIGH_LEVEL_MODELS
        ↓
active profile
        ↓
model registry
        ↓
hardware/health filtering
        ↓
adaptive router
        ↓
selected model
```

Explicit `GENERAL_MODEL`, `VISION_MODEL`, `CODING_MODEL` overrides should be disabled in production sovereign mode unless an administrator enables a documented override mechanism. This prevents accidental mismatch between the declared profile and runtime.

## Development defaults

The project should start with:

```env
SOVEREIGN_MODE=true
USE_HIGH_LEVEL_MODELS=false
```

No cloud API key should be required for the basic local demo.

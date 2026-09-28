"""Application settings loaded from environment or .env file."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Sovereign On-Premise Agentic AI Workbench."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    APP_ENV: str = "development"

    # Profile toggle (ADR-002: false by default)
    USE_HIGH_LEVEL_MODELS: bool = False

    # Sovereignty & Zero-Egress Boundary (Permanently Air-Gapped)
    SOVEREIGN_MODE: bool = True
    ALLOW_EXTERNAL_NETWORK: bool = False
    ALLOW_CLOUD_MODELS: bool = False
    ALLOW_REMOTE_TELEMETRY: bool = False
    ALLOWED_INTERNAL_HOSTS: list[str] = ["localhost", "127.0.0.1", "::1"]

    # Local Model Runtime
    MODEL_RUNTIME: str = "vllm"
    MODEL_BASE_URL: str = "http://127.0.0.1:8000/v1"
    MODEL_API_KEY: str = "local-only"
    MODEL_REQUEST_TIMEOUT_SECONDS: float = 120.0
    MODEL_HEALTH_TIMEOUT_SECONDS: float = 5.0

    # Optional explicit overrides (disabled in production sovereign mode)
    GENERAL_MODEL: str = ""
    VISION_MODEL: str = ""
    CODING_MODEL: str = ""

    # Hardware & Context
    GPU_MEMORY_UTILIZATION: float = 0.80
    MAX_CONTEXT_TOKENS: int = 16384

    # Agent Limits
    MAX_AGENT_STEPS: int = 20
    MAX_RETRIES: int = 2

    # Subsystems
    RAG_ENABLED: bool = True
    QDRANT_URL: str = "http://127.0.0.1:6333"
    OCR_ENABLED: bool = True

    # Sandbox
    SANDBOX_ENABLED: bool = True
    SANDBOX_NETWORK: str = "none"
    SANDBOX_CPU_LIMIT: int = 2
    SANDBOX_MEMORY_MB: int = 2048
    SANDBOX_TIMEOUT_SECONDS: int = 20
    SANDBOX_OUTPUT_LIMIT_KB: int = 512

    # Persistence
    DATABASE_URL: str = "postgresql://localhost/sovereign_ai"

    # Storage paths
    DATA_ROOT: str = "./data"
    ATTACHMENTS_ROOT: str = "./data/attachments"
    KNOWLEDGE_ROOT: str = "./data/knowledge"
    ARTIFACTS_ROOT: str = "./data/artifacts"
    AUDIT_ROOT: str = "./data/audit"

    # Configs directory
    CONFIGS_DIR: str = str(Path(__file__).resolve().parents[3] / "configs")


@lru_cache()
def get_settings() -> Settings:
    """Obtain cached settings instance."""
    return Settings()

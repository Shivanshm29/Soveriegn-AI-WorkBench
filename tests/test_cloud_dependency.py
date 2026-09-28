"""Test Group H: Zero Cloud Dependency and Code Auditing."""

from pathlib import Path
import re
import pytest

FORBIDDEN_CLOUD_PATTERNS = [
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"generativelanguage\.googleapis\.com",
    r"bedrock-runtime\.",
    r"api\.together\.xyz",
    r"api\.groq\.com",
    r"api\.cohere\.ai",
]


def test_zero_cloud_endpoints_in_backend():
    """Scan all backend/app/ source files to ensure no hardcoded cloud AI endpoints exist."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend" / "app"
    assert backend_dir.exists(), f"Backend dir not found at {backend_dir}"

    py_files = list(backend_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in backend/app"

    violations = []
    for file_path in py_files:
        content = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_CLOUD_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"{file_path.name}: matches '{pattern}'")

    assert not violations, f"Forbidden cloud endpoints detected in source code: {violations}"


def test_application_initializes_without_cloud_credentials(monkeypatch):
    """Verify application modules can be imported and initialized with empty environment / no cloud keys."""
    # Ensure standard cloud env vars are stripped
    cloud_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "COHERE_API_KEY",
    ]
    for var in cloud_vars:
        monkeypatch.delenv(var, raising=False)

    from backend.app.config.settings import Settings
    from backend.app.models.runtime_factory import create_model_runtime
    from backend.app.models.registry import ModelRegistry

    settings = Settings()
    assert settings.ALLOW_CLOUD_MODELS is False
    assert settings.ALLOW_EXTERNAL_NETWORK is False

    registry = ModelRegistry(settings=settings)
    assert registry.active_profile_name == "small"

    runtime = create_model_runtime(settings)
    assert runtime is not None

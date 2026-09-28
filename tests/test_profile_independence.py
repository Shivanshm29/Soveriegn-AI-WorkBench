"""Test Group G: Profile Independence and Model Resolution."""

from backend.app.config.settings import Settings
from backend.app.models.registry import ModelRegistry
from backend.app.models.runtime_factory import create_model_runtime
from backend.app.models.schemas import ModelRequest, ChatMessage


def test_small_profile_candidates():
    """Verify USE_HIGH_LEVEL_MODELS=false registers small profile candidates."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=False)
    registry = ModelRegistry(settings=settings)

    active_models = registry.list_active_models()
    model_ids = {m.id for m in active_models}

    assert "qwen3-small" in model_ids
    assert "qwen3-vl-small" in model_ids
    assert "qwen-coder-small" in model_ids
    assert len(active_models) == 3


def test_high_profile_candidates():
    """Verify USE_HIGH_LEVEL_MODELS=true registers high profile candidates."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=True)
    registry = ModelRegistry(settings=settings)

    active_models = registry.list_active_models()
    model_ids = {m.id for m in active_models}

    assert "qwen3-high" in model_ids
    assert "qwen3-vl-high" in model_ids
    assert "qwen3-coder-high" in model_ids
    assert len(active_models) == 3


def test_runtime_code_profile_agnostic():
    """Verify that the runtime code is completely decoupled from the profile toggle."""
    # Instantiating runtime for small profile
    settings_small = Settings(USE_HIGH_LEVEL_MODELS=False)
    runtime_small = create_model_runtime(settings_small)

    # Instantiating runtime for high profile
    settings_high = Settings(USE_HIGH_LEVEL_MODELS=True)
    runtime_high = create_model_runtime(settings_high)

    # Runtime classes and interfaces are identical; model selection is performed prior to runtime invocation
    assert type(runtime_small) is type(runtime_high)
    assert runtime_small.capabilities() == runtime_high.capabilities()

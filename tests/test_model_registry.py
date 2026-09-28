"""Tests for ModelRegistry in Phase 3."""

import pytest
from backend.app.schemas.models import ModelDefinition
from backend.app.models.registry import (
    ModelRegistry,
    DuplicateModelError,
    UnknownModelError,
)


def test_model_registry_registration_and_retrieval():
    """Verify models can be registered and retrieved by ID."""
    registry = ModelRegistry()
    model = ModelDefinition(
        model_id="test-qwen",
        name="Test Qwen",
        context_window=8192,
        capabilities=["reasoning", "general"],
        input_modalities=["text"],
        output_modalities=["text"],
    )
    registry.register(model)

    assert registry.exists("test-qwen")
    retrieved = registry.get("test-qwen")
    assert retrieved is not None
    assert retrieved.model_id == "test-qwen"
    assert retrieved.context_window == 8192

    # Test get_or_raise
    assert registry.get_or_raise("test-qwen").name == "Test Qwen"


def test_model_registry_duplicate_rejection():
    """Verify duplicate model registration raises DuplicateModelError."""
    registry = ModelRegistry()
    model = ModelDefinition(
        model_id="test-model",
        name="Test Model",
        context_window=4096,
    )
    registry.register(model)

    with pytest.raises(DuplicateModelError):
        registry.register(model)

    # Overwrite works if explicitly requested
    model2 = ModelDefinition(
        model_id="test-model",
        name="Test Model Updated",
        context_window=8192,
    )
    registry.register(model2, overwrite=True)
    assert registry.get("test-model").name == "Test Model Updated"


def test_model_registry_unknown_model_error():
    """Verify unknown model queries behave properly."""
    registry = ModelRegistry()
    assert registry.get("non-existent") is None
    assert not registry.exists("non-existent")

    with pytest.raises(UnknownModelError):
        registry.get_or_raise("non-existent")

    with pytest.raises(UnknownModelError):
        registry.unregister("non-existent")


def test_model_registry_unregister():
    """Verify models can be unregistered."""
    registry = ModelRegistry()
    model = ModelDefinition(
        model_id="removable-model",
        name="Removable",
        context_window=2048,
    )
    registry.register(model)
    assert registry.exists("removable-model")

    registry.unregister("removable-model")
    assert not registry.exists("removable-model")
    assert registry.get("removable-model") is None


def test_model_registry_find_by_capability():
    """Verify discovery by capability."""
    registry = ModelRegistry()
    m1 = ModelDefinition(
        model_id="coder-1",
        name="Coder 1",
        context_window=8192,
        capabilities=["coding", "analysis"],
    )
    m2 = ModelDefinition(
        model_id="vision-1",
        name="Vision 1",
        context_window=8192,
        capabilities=["vision", "ocr"],
    )
    registry.register(m1)
    registry.register(m2)

    coding_models = registry.find_by_capability("coding")
    assert len(coding_models) == 1
    assert coding_models[0].model_id == "coder-1"

    vision_models = registry.find_by_capability("vision")
    assert len(vision_models) == 1
    assert vision_models[0].model_id == "vision-1"

    none_models = registry.find_by_capability("non-existent-cap")
    assert len(none_models) == 0


def test_model_registry_find_by_modality():
    """Verify discovery by input modality."""
    registry = ModelRegistry()
    m1 = ModelDefinition(
        model_id="text-only",
        name="Text Only",
        context_window=4096,
        input_modalities=["text"],
    )
    m2 = ModelDefinition(
        model_id="multimodal",
        name="Multimodal",
        context_window=8192,
        input_modalities=["text", "image"],
    )
    registry.register(m1)
    registry.register(m2)

    image_models = registry.find_by_modality("image")
    assert any(m.model_id == "multimodal" for m in image_models)
    text_models = registry.find_by_modality("text")
    assert any(m.model_id == "text-only" for m in text_models)


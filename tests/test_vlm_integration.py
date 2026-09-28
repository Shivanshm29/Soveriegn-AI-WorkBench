"""Test H: Vision-Language Model Integration."""

import pytest
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.orchestration.routing import TaskRouter
from backend.app.multimodal.vlm_adapter import VLMDocumentAdapter
from backend.app.multimodal.schemas import RenderedPage, OCRBlock, EvidenceType


def test_vlm_resolution_through_model_registry(tmp_path):
    # Initialize real model registry and task router
    model_registry = ModelRegistry()
    agent_registry = AgentRegistry()
    router = TaskRouter(agent_registry, model_registry)

    # Initialize VLM adapter
    adapter = VLMDocumentAdapter(
        model_registry=model_registry,
        router=router,
        model_runtime=None,  # Offline test mode
    )

    # Verify model resolution resolves through registry (NOT hardcoded)
    resolved_model = adapter.resolve_vision_model()
    assert resolved_model is not None
    # For small profile it should match the configured model from YAML, but resolved dynamically
    expected_def = model_registry.get_model_definition("vision_document")
    assert resolved_model == expected_def.model_name

    # Create dummy rendered page
    page = RenderedPage(
        document_id="doc_vlm_1",
        source_hash="hash_vlm_1",
        page_number=1,
        width=800,
        height=600,
        image_path=str(tmp_path / "page_1.png"),
    )

    ocr_blocks = [
        OCRBlock(
            block_id="b1",
            page_number=1,
            text="Compressor Stage 3 Diagram",
            confidence=0.97,
            bounding_box=[100.0, 100.0, 400.0, 150.0],
            source_hash="hash_vlm_1",
        )
    ]

    # Perform analysis
    evidence = adapter.analyze_visual_page(page, ocr_blocks, query="Explain compressor diagram")

    assert evidence.evidence_type == EvidenceType.VLM_OBSERVATION
    assert evidence.page_number == 1
    assert evidence.document_id == "doc_vlm_1"
    assert evidence.extraction_method == "vlm"
    assert "Compressor" in evidence.text or "Visual layout" in evidence.text
    assert evidence.confidence is not None

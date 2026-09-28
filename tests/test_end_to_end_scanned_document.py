"""Test O: End-to-End Scanned Document Pipeline."""

import pytest
from backend.app.multimodal.schemas import (
    DocumentInput,
    DocumentType,
    EvidenceType,
    OCRBlock,
)
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.multimodal.ocr_engine import LocalOCREngine
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.orchestration.routing import TaskRouter
from backend.app.multimodal.vlm_adapter import VLMDocumentAdapter
from tests.fixtures.multimodal_fixtures import create_scanned_pdf


def test_end_to_end_scanned_document_pipeline(tmp_path):
    # 1. Create a scanned PDF fixture (raster image embedded on page, zero digital text)
    pdf_path = str(tmp_path / "scanned_invoice.pdf")
    create_scanned_pdf(pdf_path, "INVOICE #9942: PUMP BEARING 5000 RPM")

    # 2. Ingest document
    doc_input = DocumentInput.from_file(pdf_path)
    assert len(doc_input.source_hash) == 64

    # 3. Configure OCR with deterministic output for the test image
    def deterministic_ocr(img_path, page_num):
        return [
            OCRBlock(
                block_id="block_inv_1",
                page_number=page_num,
                text="INVOICE #9942: PUMP BEARING 5000 RPM",
                confidence=0.96,
                bounding_box=[50.0, 50.0, 450.0, 100.0],
                source_hash="",
                extraction_method="paddleocr",
            )
        ]

    ocr_engine = LocalOCREngine(custom_ocr_backend=deterministic_ocr)

    # 4. Configure VLM Adapter
    model_reg = ModelRegistry()
    agent_reg = AgentRegistry()
    router = TaskRouter(agent_reg, model_reg)
    vlm_adapter = VLMDocumentAdapter(model_reg, router, model_runtime=None)

    pipeline = MultimodalDocumentPipeline(
        ocr_engine=ocr_engine,
        vlm_adapter=vlm_adapter,
    )

    # 5. Execute full end-to-end pipeline:
    # scanned PDF -> detection -> rendering -> OCR -> visual analysis -> normalization -> result
    result = pipeline.process(
        doc_input,
        enable_vlm=True,
        vlm_query="Inspect invoice total and pump specification",
    )

    assert result.document_id == doc_input.document_id
    assert result.document_type in [DocumentType.SCANNED_PDF, DocumentType.IMAGE_PDF]
    assert result.page_count >= 1

    # Check evidence types produced
    evidence_types = [e.evidence_type for e in result.evidence]
    assert EvidenceType.OCR_TEXT in evidence_types
    assert EvidenceType.LAYOUT_REGION in evidence_types
    assert EvidenceType.VLM_OBSERVATION in evidence_types

    # Verify OCR text preservation
    ocr_ev = next(e for e in result.evidence if e.evidence_type == EvidenceType.OCR_TEXT)
    assert "INVOICE #9942" in ocr_ev.text
    assert ocr_ev.confidence == 0.96
    assert ocr_ev.bounding_box == [50.0, 50.0, 450.0, 100.0]
    assert ocr_ev.extraction_method == "paddleocr"

    # Verify confidence summary
    assert "avg_confidence" in result.confidence_summary
    assert result.confidence_summary["avg_confidence"] > 0.8

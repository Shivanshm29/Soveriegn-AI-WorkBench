"""Phase 6 Comprehensive Acceptance Test Suite.

Verifies all multimodal document processing requirements and acceptance criteria.
"""

import os
import pytest
from backend.app.multimodal.schemas import (
    DocumentInput,
    DocumentType,
    EvidenceType,
    OCRBlock,
    DocumentEvidence,
)
from backend.app.multimodal.type_detector import DocumentTypeDetector
from backend.app.multimodal.pdf_processor import PDFProcessor
from backend.app.multimodal.ocr_engine import LocalOCREngine
from backend.app.multimodal.layout_analyzer import LayoutAnalyzer
from backend.app.multimodal.vlm_adapter import VLMDocumentAdapter
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.multimodal.cache import DocumentCache
from backend.app.multimodal.errors import (
    DocumentTooLargeError,
    PageLimitExceededError,
    OCRError,
)
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.routing import TaskRouter
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.planner import PlanStep
from backend.app.security.egress_sentinel import get_egress_sentinel
from tests.fixtures.multimodal_fixtures import (
    create_text_pdf,
    create_scanned_pdf,
    create_image_file,
    create_table_pdf,
    create_image_pdf,
    create_prompt_injection_pdf,
)


def test_document_input_contract_and_source_hashing(tmp_path):
    pdf_path = str(tmp_path / "contract_test.pdf")
    create_text_pdf(pdf_path, "Hashing test")

    doc_input = DocumentInput.from_file(pdf_path)
    assert doc_input.document_id is not None
    assert doc_input.filename == "contract_test.pdf"
    assert doc_input.mime_type == "application/pdf"
    assert doc_input.file_size > 0
    assert len(doc_input.source_hash) == 64


def test_document_type_detection_text_and_scanned(tmp_path):
    text_pdf = str(tmp_path / "text.pdf")
    create_text_pdf(text_pdf, "Readable digital text content.")
    result_text = DocumentTypeDetector.detect(DocumentInput.from_file(text_pdf))
    assert result_text.detected_type == DocumentType.TEXT_PDF
    assert result_text.has_extractable_text is True

    scanned_pdf = str(tmp_path / "scanned.pdf")
    create_scanned_pdf(scanned_pdf, "Scanned Image Only")
    result_scanned = DocumentTypeDetector.detect(DocumentInput.from_file(scanned_pdf))
    assert result_scanned.detected_type in [DocumentType.SCANNED_PDF, DocumentType.IMAGE_PDF]
    assert result_scanned.has_extractable_text is False


def test_pdf_extraction_rendering_and_ocr(tmp_path):
    pdf_path = str(tmp_path / "sample.pdf")
    create_text_pdf(pdf_path, "Valve Pressure: 42.0 Bar")
    doc_input = DocumentInput.from_file(pdf_path)

    proc = PDFProcessor(cache_dir=str(tmp_path / "cache"))
    blocks = proc.extract_text_blocks(doc_input)
    assert len(blocks) > 0
    assert "42.0 Bar" in blocks[0].text
    assert len(blocks[0].bounding_box) == 4
    assert blocks[0].confidence == 1.0

    rendered = proc.render_all_pages(doc_input)
    assert len(rendered) == 1
    assert os.path.exists(rendered[0].image_path)
    assert rendered[0].width > 0
    assert rendered[0].height > 0


def test_local_ocr_coordinates_and_confidence(tmp_path):
    img_path = str(tmp_path / "ocr.png")
    create_image_file(img_path, "SPEED: 3000 RPM")

    def custom_ocr(path, page_num):
        return [
            OCRBlock(
                block_id="b1",
                page_number=page_num,
                text="SPEED: 3000 RPM",
                confidence=0.98,
                bounding_box=[10.0, 10.0, 200.0, 40.0],
                source_hash="",
                extraction_method="paddleocr",
            )
        ]

    engine = LocalOCREngine(custom_ocr_backend=custom_ocr)
    page_dummy = proc_page = PDFProcessor(cache_dir=str(tmp_path / "cache")).render_page(
        DocumentInput.from_file(create_text_pdf(str(tmp_path / "dummy.pdf"))), 1
    )
    blocks = engine.process_rendered_page(page_dummy)
    assert len(blocks) == 1
    assert blocks[0].bounding_box == [10.0, 10.0, 200.0, 40.0]
    assert blocks[0].confidence == 0.98


def test_layout_normalization_and_table_handling(tmp_path):
    table_pdf = str(tmp_path / "tab.pdf")
    create_table_pdf(table_pdf)
    doc_input = DocumentInput.from_file(table_pdf)

    proc = PDFProcessor()
    tables = proc.extract_tables(doc_input)
    ocr_blocks = proc.extract_text_blocks(doc_input)

    regions = LayoutAnalyzer.analyze_page(
        page_number=1,
        ocr_blocks=ocr_blocks,
        table_blocks=tables,
        source_hash=doc_input.source_hash,
    )
    assert len(regions) > 0
    for r in regions:
        assert len(r.bounding_box) == 4
        assert r.page_number == 1


def test_image_extraction(tmp_path):
    img_pdf = str(tmp_path / "with_fig.pdf")
    create_image_pdf(img_pdf)
    doc_input = DocumentInput.from_file(img_pdf)

    proc = PDFProcessor()
    images = proc.extract_images(doc_input)
    assert len(images) > 0
    assert images[0].page_number == 1
    assert len(images[0].bounding_box) == 4


def test_vlm_integration_no_hardcoded_models(tmp_path):
    model_reg = ModelRegistry()
    agent_reg = AgentRegistry()
    router = TaskRouter(agent_reg, model_reg)
    adapter = VLMDocumentAdapter(model_reg, router, model_runtime=None)

    resolved = adapter.resolve_vision_model()
    # Confirms dynamic resolution from registry
    assert resolved == model_reg.get_model_definition("vision_document").model_name


def test_prompt_injection_is_quarantined_as_data(tmp_path):
    inj_pdf = str(tmp_path / "injection.pdf")
    create_prompt_injection_pdf(inj_pdf)

    pipeline = MultimodalDocumentPipeline()
    result = pipeline.process(DocumentInput.from_file(inj_pdf), enable_vlm=False)

    assert len(result.warnings) > 0
    assert any("Prompt injection" in w for w in result.warnings)

    quarantined = [e for e in result.evidence if "DOCUMENT_DATA_QUARANTINE" in (e.text or "")]
    assert len(quarantined) > 0


def test_agent_and_tool_registry_integration(tmp_path):
    tool_reg = ToolRegistry(include_multimodal=True)
    assert tool_reg.exists("document_type_detect")
    assert tool_reg.exists("pdf_text_extract")
    assert tool_reg.exists("pdf_render")
    assert tool_reg.exists("layout_analyze")
    assert tool_reg.exists("table_extract")
    assert tool_reg.exists("image_extract")
    assert tool_reg.exists("vlm_analyze_document")

    agent_reg = AgentRegistry()
    executor = AgentExecutor(agent_reg, tool_reg)

    pdf_path = str(tmp_path / "doc.pdf")
    create_text_pdf(pdf_path, "Coolant Temperature: 85 C")

    step = PlanStep(
        step_id="s1",
        agent_id="document_agent",
        capability="pdf_ingestion",
        description="Ingest document",
        required_tools=["document_type_detect", "pdf_text_extract"],
        expected_output="Evidence",
    )
    res = executor.execute("document_agent", step, {"document_path": pdf_path})
    assert res.status == "SUCCESS"
    assert "document_analysis" in res.output


def test_sovereignty_zero_egress_enforced(tmp_path):
    pdf_path = str(tmp_path / "sov.pdf")
    create_text_pdf(pdf_path, "Sovereign Air-Gapped Data")

    pipeline = MultimodalDocumentPipeline()
    sentinel = get_egress_sentinel()
    ext_before = sentinel.external_connections_successful

    pipeline.process(DocumentInput.from_file(pdf_path), enable_vlm=False)
    assert sentinel.external_connections_successful == ext_before == 0


def test_resource_limits_and_safe_caching(tmp_path):
    pdf_path = str(tmp_path / "limit.pdf")
    create_text_pdf(pdf_path, "Data")

    # Resource limit: file size
    small_proc = PDFProcessor(max_file_size_bytes=10)
    with pytest.raises(DocumentTooLargeError):
        small_proc.extract_text_blocks(DocumentInput.from_file(pdf_path))

    # Caching
    cache = DocumentCache(cache_dir=str(tmp_path / "cache_test"))
    pipe = MultimodalDocumentPipeline(cache=cache)

    doc = DocumentInput.from_file(pdf_path)
    res1 = pipe.process(doc, enable_vlm=False)
    assert res1.processing_metadata["cached"] is False

    res2 = pipe.process(doc, enable_vlm=False)
    assert res2.processing_metadata["cached"] is True


def test_no_fake_ocr_success_on_failure(tmp_path):
    img_path = str(tmp_path / "fail.png")
    create_image_file(img_path, "FAIL")

    page = PDFProcessor(cache_dir=str(tmp_path / "cache")).render_page(
        DocumentInput.from_file(create_text_pdf(str(tmp_path / "p.pdf"))), 1
    )
    engine = LocalOCREngine(simulate_failure=True)
    with pytest.raises(OCRError):
        engine.process_rendered_page(page)

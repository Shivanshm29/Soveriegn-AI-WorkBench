"""Test I: Multimodal Evidence Normalization."""

import pytest
from backend.app.multimodal.schemas import DocumentInput, DocumentEvidence, EvidenceType
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from tests.fixtures.multimodal_fixtures import create_text_pdf


def test_evidence_normalization_contract(tmp_path):
    pdf_path = str(tmp_path / "evidence_norm.pdf")
    create_text_pdf(pdf_path, "System specifications: Flow rate 500 L/min.")

    doc_input = DocumentInput.from_file(pdf_path)
    pipeline = MultimodalDocumentPipeline()

    result = pipeline.process(doc_input, enable_vlm=False)

    assert len(result.evidence) > 0
    assert result.document_id == doc_input.document_id
    assert result.source_hash == doc_input.source_hash

    for ev in result.evidence:
        assert isinstance(ev, DocumentEvidence)
        assert ev.document_id == doc_input.document_id
        assert ev.source_hash == doc_input.source_hash
        assert ev.page_number >= 1
        assert isinstance(ev.evidence_type, EvidenceType)
        assert ev.extraction_method != ""
        if ev.confidence is not None:
            assert 0.0 <= ev.confidence <= 1.0

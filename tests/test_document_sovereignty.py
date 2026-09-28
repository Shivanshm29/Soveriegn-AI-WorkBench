"""Test K: Document Pipeline Zero-Egress Sovereignty."""

import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.security.egress_sentinel import get_egress_sentinel
from tests.fixtures.multimodal_fixtures import create_text_pdf, create_scanned_pdf


def test_document_pipeline_performs_zero_egress(tmp_path):
    pdf_path = str(tmp_path / "sovereign_doc.pdf")
    create_text_pdf(pdf_path, "Air-gapped confidential engineering doc.")

    doc_input = DocumentInput.from_file(pdf_path)
    pipeline = MultimodalDocumentPipeline()

    sentinel = get_egress_sentinel()
    successful_before = sentinel.external_connections_successful
    blocked_before = sentinel.blocked_egress_attempts

    # Execute full pipeline
    result = pipeline.process(doc_input, enable_vlm=False)

    assert result.document_id == doc_input.document_id
    assert len(result.evidence) > 0

    # Ensure zero external network connections occurred
    assert sentinel.external_connections_successful == successful_before == 0
    assert sentinel.blocked_egress_attempts == blocked_before

"""Test L: Source Hash Validation and Safe Caching."""

import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.multimodal.cache import DocumentCache
from tests.fixtures.multimodal_fixtures import create_text_pdf


def test_modified_document_changes_hash_and_invalidates_cache(tmp_path):
    pdf_path = str(tmp_path / "dynamic_doc.pdf")
    create_text_pdf(pdf_path, "Original Version: 1.0.0")

    cache = DocumentCache(cache_dir=str(tmp_path / "test_cache"))
    pipeline = MultimodalDocumentPipeline(cache=cache)

    doc_v1 = DocumentInput.from_file(pdf_path)
    result_v1 = pipeline.process(doc_v1, enable_vlm=False)
    hash_v1 = doc_v1.source_hash

    assert result_v1.source_hash == hash_v1
    assert result_v1.processing_metadata.get("cached") is False

    # Second run with exact same file uses cache
    result_cached = pipeline.process(doc_v1, enable_vlm=False)
    assert result_cached.processing_metadata.get("cached") is True

    # Mutate the source document
    create_text_pdf(pdf_path, "Modified Version: 2.0.0 with new metrics")
    doc_v2 = DocumentInput.from_file(pdf_path)
    hash_v2 = doc_v2.source_hash

    # Hashes MUST differ
    assert hash_v1 != hash_v2

    # Processing mutated document MUST NOT use old cached result
    result_v2 = pipeline.process(doc_v2, enable_vlm=False)
    assert result_v2.source_hash == hash_v2
    assert result_v2.processing_metadata.get("cached") is False

    extracted_text = " ".join([e.text or "" for e in result_v2.evidence])
    assert "Modified Version" in extracted_text
    assert "Original Version" not in extracted_text

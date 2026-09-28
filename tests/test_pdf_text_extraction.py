"""Test B: PDF Text Extraction."""

import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pdf_processor import PDFProcessor
from tests.fixtures.multimodal_fixtures import create_text_pdf


def test_pdf_text_extraction_and_mapping(tmp_path):
    pdf_path = str(tmp_path / "multi_page.pdf")
    content = "Page One: Critical Operating Parameters.\nPressure: 14.2 MPa."
    create_text_pdf(pdf_path, content)

    doc_input = DocumentInput.from_file(pdf_path)
    assert len(doc_input.source_hash) == 64  # Valid SHA-256

    processor = PDFProcessor()
    blocks = processor.extract_text_blocks(doc_input)

    assert len(blocks) > 0
    extracted_text = " ".join([b.text for b in blocks])
    assert "Operating Parameters" in extracted_text
    assert "14.2 MPa" in extracted_text

    # Verify block properties
    first_block = blocks[0]
    assert first_block.page_number == 1
    assert first_block.source_hash == doc_input.source_hash
    assert first_block.confidence == 1.0
    assert len(first_block.bounding_box) == 4
    assert first_block.extraction_method == "native_text"

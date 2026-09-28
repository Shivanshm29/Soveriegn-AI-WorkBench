"""Test M: Resource Limits and Bound Constraints."""

import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pdf_processor import PDFProcessor
from backend.app.multimodal.errors import DocumentTooLargeError, PageLimitExceededError
from tests.fixtures.multimodal_fixtures import create_text_pdf


def test_oversized_document_raises_controlled_error(tmp_path):
    pdf_path = str(tmp_path / "normal.pdf")
    create_text_pdf(pdf_path, "Content")

    doc_input = DocumentInput.from_file(pdf_path)
    # Configure processor with small max size (e.g. 100 bytes)
    processor = PDFProcessor(max_file_size_bytes=100)

    with pytest.raises(DocumentTooLargeError) as exc_info:
        processor.extract_text_blocks(doc_input)

    assert exc_info.value.max_allowed == 100
    assert exc_info.value.file_size > 100


def test_excessive_page_count_raises_controlled_error(tmp_path):
    pdf_path = str(tmp_path / "pages.pdf")
    create_text_pdf(pdf_path, "One Page")

    doc_input = DocumentInput.from_file(pdf_path)
    # Configure processor with 0 max pages limit
    processor = PDFProcessor(max_page_count=0)

    with pytest.raises(PageLimitExceededError) as exc_info:
        processor.open_doc(doc_input.source_path)

    assert exc_info.value.max_allowed == 0

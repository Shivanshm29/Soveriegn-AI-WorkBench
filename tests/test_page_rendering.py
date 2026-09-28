"""Test C: Local Page Rendering."""

import os
import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pdf_processor import PDFProcessor
from tests.fixtures.multimodal_fixtures import create_text_pdf


def test_pdf_page_rendering(tmp_path):
    pdf_path = str(tmp_path / "render_test.pdf")
    create_text_pdf(pdf_path, "Rendering verification page.")
    cache_dir = str(tmp_path / "cache")

    doc_input = DocumentInput.from_file(pdf_path)
    processor = PDFProcessor(cache_dir=cache_dir, render_dpi=150)

    rendered_pages = processor.render_all_pages(doc_input)
    assert len(rendered_pages) == 1

    page = rendered_pages[0]
    assert page.page_number == 1
    assert page.document_id == doc_input.document_id
    assert page.source_hash == doc_input.source_hash
    assert page.width > 0
    assert page.height > 0
    assert os.path.exists(page.image_path)
    assert page.image_path.endswith(".png")

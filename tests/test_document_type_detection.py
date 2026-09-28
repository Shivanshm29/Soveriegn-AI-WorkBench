"""Test A: Document Type Detection."""

import os
import pytest
from backend.app.multimodal.schemas import DocumentInput, DocumentType
from backend.app.multimodal.type_detector import DocumentTypeDetector
from tests.fixtures.multimodal_fixtures import (
    create_text_pdf,
    create_scanned_pdf,
    create_image_file,
    create_malformed_pdf,
)


def test_text_pdf_detection(tmp_path):
    pdf_path = str(tmp_path / "sample_text.pdf")
    create_text_pdf(pdf_path, "Standard digital text document.")
    doc_input = DocumentInput.from_file(pdf_path)

    result = DocumentTypeDetector.detect(doc_input)
    assert result.detected_type == DocumentType.TEXT_PDF
    assert result.has_extractable_text is True
    assert result.page_count >= 1
    assert result.confidence == 1.0


def test_scanned_pdf_detection(tmp_path):
    pdf_path = str(tmp_path / "scanned_doc.pdf")
    create_scanned_pdf(pdf_path, "SCANNED TEXT 12.4 MPa")
    doc_input = DocumentInput.from_file(pdf_path)

    result = DocumentTypeDetector.detect(doc_input)
    assert result.detected_type in [DocumentType.SCANNED_PDF, DocumentType.IMAGE_PDF]
    assert result.has_extractable_text is False
    assert result.has_images is True
    assert result.page_count >= 1


def test_image_file_detection(tmp_path):
    img_path = str(tmp_path / "diagram.png")
    create_image_file(img_path, "SENSOR DIAGRAM")
    doc_input = DocumentInput.from_file(img_path)

    result = DocumentTypeDetector.detect(doc_input)
    assert result.detected_type == DocumentType.IMAGE
    assert result.page_count == 1
    assert result.has_images is True


def test_unsupported_file_detection(tmp_path):
    txt_path = str(tmp_path / "unsupported.bin")
    with open(txt_path, "wb") as f:
        f.write(b"\x00\x01\x02\x03\x04\x05rawbinary")
    doc_input = DocumentInput.from_file(txt_path)

    result = DocumentTypeDetector.detect(doc_input)
    assert result.detected_type == DocumentType.UNSUPPORTED
    assert result.confidence == 0.0

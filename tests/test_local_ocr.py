"""Test D: Local OCR Extraction."""

import os
import pytest
from backend.app.multimodal.schemas import RenderedPage, OCRBlock
from backend.app.multimodal.ocr_engine import LocalOCREngine
from tests.fixtures.multimodal_fixtures import create_image_file


def test_local_ocr_preserves_coordinates_and_confidence(tmp_path):
    img_path = str(tmp_path / "scanned_text.png")
    create_image_file(img_path, "Operating Pressure: 12.4 MPa")

    page = RenderedPage(
        document_id="doc_test_ocr",
        source_hash="hash_12345",
        page_number=3,
        width=600,
        height=400,
        image_path=img_path,
    )

    # Test with custom deterministic OCR backend simulating local PaddleOCR coordinates
    def mock_ocr(path, page_num):
        return [
            OCRBlock(
                block_id="b1",
                page_number=page_num,
                text="Operating Pressure: 12.4 MPa",
                confidence=0.96,
                bounding_box=[50.0, 50.0, 320.0, 80.0],
                source_hash="",
                extraction_method="paddleocr",
            )
        ]

    engine = LocalOCREngine(custom_ocr_backend=mock_ocr)
    blocks = engine.process_rendered_page(page)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.page_number == 3
    assert block.source_hash == "hash_12345"
    assert block.text == "Operating Pressure: 12.4 MPa"
    assert block.confidence == 0.96
    assert block.bounding_box == [50.0, 50.0, 320.0, 80.0]
    assert block.extraction_method == "paddleocr"

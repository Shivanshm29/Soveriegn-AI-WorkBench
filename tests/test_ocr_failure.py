"""Test E: OCR Failure Handling."""

import pytest
from backend.app.multimodal.schemas import RenderedPage
from backend.app.multimodal.ocr_engine import LocalOCREngine
from backend.app.multimodal.errors import OCRError
from tests.fixtures.multimodal_fixtures import create_image_file


def test_ocr_simulated_failure_raises_structured_error(tmp_path):
    img_path = str(tmp_path / "corrupted_page.png")
    create_image_file(img_path, "TEST")

    page = RenderedPage(
        document_id="doc_fail",
        source_hash="hash_fail",
        page_number=2,
        width=500,
        height=500,
        image_path=img_path,
    )

    engine = LocalOCREngine(simulate_failure=True)

    with pytest.raises(OCRError) as exc_info:
        engine.process_rendered_page(page)

    assert exc_info.value.page_number == 2
    assert "Simulated OCR failure" in str(exc_info.value)
    # Ensure no fake text was returned

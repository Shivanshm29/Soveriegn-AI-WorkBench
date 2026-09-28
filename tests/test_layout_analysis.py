"""Test F: Document Layout Analysis."""

import pytest
from backend.app.multimodal.schemas import OCRBlock, TableBlock, ImageBlock
from backend.app.multimodal.layout_analyzer import LayoutAnalyzer


def test_layout_analysis_categorization():
    page_number = 1
    ocr_blocks = [
        OCRBlock(
            block_id="b1",
            page_number=page_number,
            text="1.0 EXECUTIVE SUMMARY",
            confidence=0.99,
            bounding_box=[50.0, 70.0, 300.0, 90.0],
            source_hash="h1",
            extraction_method="native_text",
        ),
        OCRBlock(
            block_id="b2",
            page_number=page_number,
            text="This section describes the detailed operating conditions of the facility over a 24-hour monitoring cycle.",
            confidence=0.98,
            bounding_box=[50.0, 100.0, 500.0, 140.0],
            source_hash="h1",
            extraction_method="native_text",
        ),
        OCRBlock(
            block_id="b3",
            page_number=page_number,
            text="- Turbine Inlet 1\n- Turbine Inlet 2",
            confidence=0.95,
            bounding_box=[50.0, 150.0, 200.0, 180.0],
            source_hash="h1",
            extraction_method="native_text",
        ),
    ]

    table_blocks = [
        TableBlock(
            table_id="t1",
            page_number=page_number,
            bounding_box=[50.0, 200.0, 450.0, 350.0],
            rows=[["Inlet", "12.4 MPa"], ["Outlet", "1.2 MPa"]],
            headers=["Parameter", "Value"],
            confidence=0.95,
            source_hash="h1",
        )
    ]

    image_blocks = [
        ImageBlock(
            image_id="img1",
            page_number=page_number,
            bounding_box=[50.0, 400.0, 300.0, 550.0],
            source_hash="h1",
            image_reference="Figure 1: Sensor Array",
            extraction_method="pymupdf",
            confidence=1.0,
        )
    ]

    regions = LayoutAnalyzer.analyze_page(
        page_number=page_number,
        ocr_blocks=ocr_blocks,
        table_blocks=table_blocks,
        image_blocks=image_blocks,
        source_hash="h1",
    )

    region_types = [r.region_type for r in regions]
    assert "heading" in region_types
    assert "paragraph" in region_types
    assert "list" in region_types
    assert "table" in region_types
    assert "figure" in region_types or "image" in region_types

    # Ensure all regions preserve coordinates and page number
    for r in regions:
        assert r.page_number == 1
        assert len(r.bounding_box) == 4

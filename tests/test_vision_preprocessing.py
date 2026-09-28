"""Tests for Phase 7 local image preprocessing, tiling, and region detection."""

import os
import pytest
from PIL import Image

from backend.app.vision.preprocessing import ImagePreprocessor
from backend.app.vision.region_detector import VisualRegionDetector
from backend.app.vision.errors import (
    CorruptImageError,
    OversizedImageError,
    UnsupportedImageFormatError,
    TileGenerationError,
)
from tests.fixtures.vision_fixtures import (
    create_simple_drawing,
    create_large_tiling_drawing,
    create_malformed_image,
)


def test_image_ingestion_and_validation(tmp_path):
    """Test image format validation, corruption detection, and dimensions."""
    preproc = ImagePreprocessor(max_dimension=4000)

    # Valid PNG
    valid_path = str(tmp_path / "valid.png")
    create_simple_drawing(valid_path, width=800, height=600)
    w, h, fmt = preproc.validate_image(valid_path)
    assert w == 800
    assert h == 600
    assert fmt == "PNG"

    # Corrupt / Malformed file
    corrupt_path = str(tmp_path / "corrupt.png")
    create_malformed_image(corrupt_path)
    with pytest.raises(CorruptImageError):
        preproc.validate_image(corrupt_path)

    # Non-existent file
    with pytest.raises(FileNotFoundError):
        preproc.validate_image(str(tmp_path / "non_existent.jpg"))


def test_oversized_image_rejection(tmp_path):
    """Test resource limits: oversized image raises OversizedImageError."""
    preproc = ImagePreprocessor(max_dimension=500)
    large_path = str(tmp_path / "too_large.png")
    create_simple_drawing(large_path, width=600, height=600)

    with pytest.raises(OversizedImageError):
        preproc.validate_image(large_path)


def test_preprocessing_transformations(tmp_path):
    """Test contrast enhancement, grayscale conversion, and denoising."""
    preproc = ImagePreprocessor()
    img_path = str(tmp_path / "sample.png")
    create_simple_drawing(img_path, width=400, height=300)

    orig_img = Image.open(img_path)
    processed_img, meta = preproc.preprocess(
        orig_img,
        to_grayscale=True,
        normalize_contrast=True,
        denoise=True,
    )

    assert processed_img.mode == "L"  # Grayscale
    assert meta["converted_grayscale"] is True
    assert meta["contrast_normalized"] is True
    assert meta["denoised"] is True
    assert processed_img.size == (400, 300)


def test_drawing_tiling_with_coordinate_mapping(tmp_path):
    """Test large drawing tiling retaining original coordinate bounding boxes."""
    preproc = ImagePreprocessor(max_tiles=16)
    large_path = str(tmp_path / "large_dwg.png")
    create_large_tiling_drawing(large_path, width=2400, height=2400)

    img = Image.open(large_path)
    tiles = preproc.generate_tiles(
        img,
        document_id="doc_large_01",
        source_hash="hash_abc123",
        tile_size=1000,
        overlap=100,
    )

    assert len(tiles) > 1
    assert len(tiles) <= 16

    # Verify tile coordinate consistency
    for tile in tiles:
        assert tile.document_id == "doc_large_01"
        assert tile.source_hash == "hash_abc123"
        assert tile.original_dimensions == (2400, 2400)
        x0, y0, x1, y1 = tile.bounding_box
        assert 0 <= x0 <= x1 <= 2400
        assert 0 <= y0 <= y1 <= 2400
        assert os.path.exists(tile.tile_path)


def test_tiling_resource_limit_failure(tmp_path):
    """Test that requesting too many tiles fails safely with TileGenerationError."""
    preproc = ImagePreprocessor(max_tiles=4)
    large_path = str(tmp_path / "huge.png")
    create_large_tiling_drawing(large_path, width=2400, height=2400)

    img = Image.open(large_path)
    # tile_size=400 on 2400x2400 would generate ~36 tiles, exceeding max_tiles=4
    with pytest.raises(TileGenerationError):
        preproc.generate_tiles(img, "doc_huge", "hash_huge", tile_size=400)


def test_visual_region_detector_structural_regions(tmp_path):
    """Test detection of title block, drawing body, notes, and unknown regions."""
    detector = VisualRegionDetector()
    dwg_path = str(tmp_path / "dwg_sample.png")
    create_simple_drawing(dwg_path, width=1200, height=800)

    img = Image.open(dwg_path)
    ocr_mock_blocks = [
        {"text": "DWG NO: TC-2026-X1 PROJECT: TURBINE", "bbox": [800, 680, 1150, 770], "confidence": 0.95},
        {"text": "100.0 ± 0.1 mm Ø 50 H7", "bbox": [200, 100, 450, 150], "confidence": 0.90},
        {"text": "GENERAL NOTES: ALL DIMENSIONS IN MM", "bbox": [800, 50, 1150, 200], "confidence": 0.88},
    ]

    regions = detector.detect_regions(
        image=img,
        ocr_blocks=ocr_mock_blocks,
        source_hash="hash_test",
        page_number=1,
    )

    assert len(regions) >= 3
    types = [r.region_type for r in regions]
    assert "title_block" in types
    assert "drawing_body" in types

    for r in regions:
        assert r.confidence is not None
        assert len(r.bounding_box) == 4
        x0, y0, x1, y1 = r.bounding_box
        assert 0 <= x0 <= x1 <= 1200
        assert 0 <= y0 <= y1 <= 800

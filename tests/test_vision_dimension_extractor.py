"""Tests for dimension extraction, tolerance detection, and zero-hallucination guarantees."""

import pytest
from backend.app.vision.dimension_extractor import DimensionExtractor
from backend.app.vision.schemas import (
    EngineeringEvidenceType,
    ConfidenceLevel,
)


def test_linear_dimension_extraction():
    """Test standard linear dimensions with unit detection."""
    extractor = DimensionExtractor()
    dims = extractor.extract_from_text("100.5 mm\n75.0 in\n50")

    assert len(dims) == 3
    assert dims[0].value == 100.5
    assert dims[0].unit == "mm"
    assert dims[0].confidence.level == ConfidenceLevel.HIGH

    assert dims[1].value == 75.0
    assert dims[1].unit == "in"

    assert dims[2].value == 50.0
    assert dims[2].unit == "mm"  # Default engineering unit


def test_toleranced_dimension_extraction():
    """Test symmetric and bilateral tolerance parsing."""
    extractor = DimensionExtractor()

    # Symmetric tolerance
    dims = extractor.extract_from_text("50.0 ± 0.05 mm")
    assert len(dims) == 1
    assert dims[0].value == 50.0
    assert dims[0].tolerance == "±0.05"
    assert dims[0].unit == "mm"

    # Bilateral tolerance
    dims = extractor.extract_from_text("25.0 +0.1/-0.0 mm")
    assert len(dims) == 1
    assert dims[0].value == 25.0
    assert dims[0].tolerance == "+0.1/-0.0"

    # ISO Fit Class tolerance
    dims = extractor.extract_from_text("Ø 40 H7")
    assert len(dims) == 1
    assert dims[0].value == 40.0
    assert dims[0].feature_type == "diameter"
    assert dims[0].tolerance == "H7"


def test_special_features_diameter_radius_thread():
    """Test diameter symbol, radius, thread, and quantity multipliers."""
    extractor = DimensionExtractor()

    # Diameter
    dims = extractor.extract_from_text("Ø 50.0")
    assert dims[0].feature_type == "diameter"
    assert dims[0].value == 50.0

    # Radius
    dims = extractor.extract_from_text("R 12.5 mm")
    assert dims[0].feature_type == "radius"
    assert dims[0].value == 12.5

    # Quantity
    dims = extractor.extract_from_text("4x M6")
    assert dims[0].feature_type == "thread"
    assert dims[0].value == 6.0


def test_zero_hallucination_on_ambiguous_or_unreadable():
    """Section 9 Rule: If system cannot confidently read a value: value = None and record uncertainty."""
    extractor = DimensionExtractor()

    ambiguous_samples = [
        "approx 25 mm",
        "approximately looks like 25",
        "~50 mm",
        "blurred text ?? mm",
        "estimated 100",
    ]

    for sample in ambiguous_samples:
        dims = extractor.extract_from_text(sample)
        assert len(dims) >= 1
        assert dims[0].value is None, f"Expected value=None for ambiguous sample '{sample}'"
        assert dims[0].confidence.level in (ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN)
        assert dims[0].uncertainty is not None


def test_conversion_to_engineering_evidence():
    """Test converting parsed dimensions to EngineeringEvidence objects."""
    extractor = DimensionExtractor()
    dims = extractor.extract_from_text("100.0 ± 0.1 mm")
    evs = extractor.to_engineering_evidence(
        dimensions=dims,
        document_id="doc_dim_test",
        source_hash="hash_dim_001",
        page_number=1,
        region_id="reg_dim_001",
    )

    assert len(evs) == 1
    ev = evs[0]
    assert ev.evidence_type == EngineeringEvidenceType.DIMENSION
    assert ev.document_id == "doc_dim_test"
    assert ev.source_hash == "hash_dim_001"
    assert ev.region_id == "reg_dim_001"
    assert ev.visual_features["value"] == 100.0
    assert ev.visual_features["tolerance"] == "±0.1"
    assert ev.confidence.level == ConfidenceLevel.HIGH

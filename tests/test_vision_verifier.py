"""Tests for deterministic verification of visual evidence and vision results."""

import pytest
from backend.app.vision.verifier import VisualEvidenceVerifier
from backend.app.vision.schemas import (
    EngineeringVisionResult,
    EngineeringEvidence,
    EngineeringEvidenceType,
    VisualObservation,
    EngineeringFinding,
    VisualRegion,
    ConfidenceAssessment,
    ConfidenceLevel,
)


def _build_valid_vision_result() -> EngineeringVisionResult:
    """Helper to construct a valid EngineeringVisionResult."""
    source_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
    conf = ConfidenceAssessment(value=0.9, level=ConfidenceLevel.HIGH, rationale="Deterministic test")

    reg = VisualRegion(
        region_id="reg_01",
        page_number=1,
        region_type="drawing_body",
        bounding_box=[100.0, 100.0, 500.0, 500.0],
        confidence=conf,
        source_hash=source_hash,
    )

    ev = EngineeringEvidence(
        evidence_id="ev_01",
        document_id="doc_01",
        source_hash=source_hash,
        page_number=1,
        region_id="reg_01",
        evidence_type=EngineeringEvidenceType.DIMENSION,
        bounding_box=[120.0, 120.0, 300.0, 180.0],
        observation="Extracted dimension 100 mm",
        confidence=conf,
    )

    obs = VisualObservation(
        observation_id="obs_01",
        region_id="reg_01",
        observation="Dimension 100 mm observed",
        interpretation="Nominal dimension is 100 mm",
        uncertainty="None",
        confidence=conf,
        evidence_refs=["ev_01"],
    )

    finding = EngineeringFinding(
        finding_id="find_01",
        title="Candidate dimension indication",
        description="Observed 100 mm nominal dimension",
        finding_type="dimension_indication",
        confidence=conf,
        evidence_ids=["ev_01"],
    )

    return EngineeringVisionResult(
        task_id="task_test_01",
        document_id="doc_01",
        source_hash=source_hash,
        analyzed_regions=[reg],
        evidence=[ev],
        observations=[obs],
        findings=[finding],
    )


def test_valid_vision_result_verification():
    """Test that a well-formed vision result passes deterministic verification."""
    verifier = VisualEvidenceVerifier()
    res = _build_valid_vision_result()

    report = verifier.verify_result(res, expected_source_hash=res.source_hash)

    assert report.is_valid is True
    assert report.status == "VERIFIED"
    assert len(report.failed_checks) == 0
    assert res.verification_status == "VERIFIED"


def test_mismatched_source_hash_rejection():
    """Test that source hash mismatch fails verification."""
    verifier = VisualEvidenceVerifier()
    res = _build_valid_vision_result()

    report = verifier.verify_result(res, expected_source_hash="different_hash_value")

    assert report.is_valid is False
    assert report.status == "VERIFICATION_FAILED"
    assert any("Source hash mismatch" in err for err in report.failed_checks)


def test_invalid_bounding_box_rejection():
    """Test that inverted or out-of-bounds bounding boxes fail verification."""
    verifier = VisualEvidenceVerifier()
    res = _build_valid_vision_result()

    # Invert coordinates: x0 > x1
    res.evidence[0].bounding_box = [500.0, 100.0, 200.0, 400.0]

    report = verifier.verify_result(res)

    assert report.is_valid is False
    assert any("invalid bounding box" in err for err in report.failed_checks)


def test_nonexistent_evidence_reference_rejection():
    """Section 16: No observation or finding references nonexistent evidence."""
    verifier = VisualEvidenceVerifier()
    res = _build_valid_vision_result()

    # Observation references a ghost evidence ID
    res.observations[0].evidence_refs.append("ev_ghost_nonexistent_999")

    report = verifier.verify_result(res)

    assert report.is_valid is False
    assert any("nonexistent evidence ID 'ev_ghost_nonexistent_999'" in err for err in report.failed_checks)


def test_forbidden_certified_claims_in_findings_rejection():
    """Ensure verifier catches forbidden certified claims."""
    verifier = VisualEvidenceVerifier()
    res = _build_valid_vision_result()

    res.findings[0].title = "Certified safe component"

    report = verifier.verify_result(res)

    assert report.is_valid is False
    assert any("forbidden unverified diagnostic claim" in err for err in report.failed_checks)

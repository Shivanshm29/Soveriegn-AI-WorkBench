"""Deterministic verifier for engineering drawing and industrial vision analysis results."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.app.vision.schemas import (
    EngineeringVisionResult,
    EngineeringEvidence,
    VisualObservation,
    EngineeringFinding,
    ConfidenceLevel,
)
from backend.app.vision.errors import (
    VisualVerificationError,
    InvalidBoundingBoxError,
    MissingEvidenceError,
)


class VerificationReport(BaseModel):
    """Detailed report summarizing deterministic verification checks."""

    is_valid: bool
    status: str  # "VERIFIED", "VERIFICATION_FAILED", "VERIFIED_WITH_WARNINGS"
    total_checks: int
    passed_checks: int
    failed_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class VisualEvidenceVerifier:
    """Verifies evidence linkage, bounding box geometry, confidence metrics, and source hashes."""

    def verify_result(
        self,
        result: EngineeringVisionResult,
        expected_source_hash: Optional[str] = None,
        max_image_dimensions: Optional[tuple] = None,
    ) -> VerificationReport:
        """Run complete suite of deterministic verification checks on an EngineeringVisionResult."""
        failed: List[str] = []
        warnings: List[str] = []
        checks_count = 0

        # 1. Source Hash Integrity
        checks_count += 1
        if not result.source_hash:
            failed.append("Missing source_hash on vision result.")
        elif expected_source_hash and result.source_hash != expected_source_hash:
            failed.append(
                f"Source hash mismatch: expected {expected_source_hash}, got {result.source_hash}."
            )

        # 2. Region Bounding Box Validity
        checks_count += 1
        region_ids = set()
        for reg in result.analyzed_regions:
            region_ids.add(reg.region_id)
            if not self._is_valid_bbox(reg.bounding_box, max_image_dimensions):
                failed.append(
                    f"Region {reg.region_id} has invalid bounding box: {reg.bounding_box}."
                )

        # 3. Evidence Bounding Boxes and Integrity
        checks_count += 1
        evidence_map: Dict[str, EngineeringEvidence] = {}
        for ev in result.evidence:
            evidence_map[ev.evidence_id] = ev
            if not self._is_valid_bbox(ev.bounding_box, max_image_dimensions):
                failed.append(
                    f"Evidence {ev.evidence_id} has invalid bounding box: {ev.bounding_box}."
                )
            # Verify region belonging
            if region_ids and ev.region_id not in region_ids and ev.region_id != "global":
                warnings.append(
                    f"Evidence {ev.evidence_id} references region {ev.region_id} which is not in analyzed_regions."
                )
            # Source hash match on evidence
            if result.source_hash and ev.source_hash and ev.source_hash != result.source_hash:
                failed.append(
                    f"Evidence {ev.evidence_id} source_hash {ev.source_hash} does not match result source_hash {result.source_hash}."
                )

        # 4. Observation Evidence References Integrity (Section 16: no observation references nonexistent evidence)
        checks_count += 1
        for obs in result.observations:
            for ref in obs.evidence_refs:
                if ref not in evidence_map:
                    failed.append(
                        f"Observation {obs.observation_id} references nonexistent evidence ID '{ref}'."
                    )
            # Confidence presence
            if not obs.confidence or obs.confidence.level == ConfidenceLevel.UNKNOWN:
                warnings.append(
                    f"Observation {obs.observation_id} has UNKNOWN or missing confidence."
                )

        # 5. Finding Evidence References Integrity
        checks_count += 1
        for finding in result.findings:
            for ev_id in finding.evidence_ids:
                if ev_id not in evidence_map:
                    failed.append(
                        f"Finding {finding.finding_id} references nonexistent evidence ID '{ev_id}'."
                    )

        # 6. Candidate Terminology Adherence
        checks_count += 1
        for finding in result.findings:
            title_lower = finding.title.lower()
            if any(forbidden in title_lower for forbidden in ["certified safe", "guaranteed broken", "confirmed defect"]):
                failed.append(
                    f"Finding {finding.finding_id} uses forbidden unverified diagnostic claim in title: '{finding.title}'."
                )

        passed_count = checks_count - len(failed)
        is_valid = len(failed) == 0

        if is_valid and warnings:
            status = "VERIFIED_WITH_WARNINGS"
        elif is_valid:
            status = "VERIFIED"
        else:
            status = "VERIFICATION_FAILED"

        # Update the result directly
        result.verification_status = status
        result.verification_required = True  # Always requires human sign-off per industrial standard
        result.verification_summary = (
            f"Deterministic verification {status}: {passed_count}/{checks_count} checks passed."
        )
        if failed:
            result.verification_summary += f" Failures: {'; '.join(failed[:3])}"

        return VerificationReport(
            is_valid=is_valid,
            status=status,
            total_checks=checks_count,
            passed_checks=passed_count,
            failed_checks=failed,
            warnings=warnings,
            details={
                "analyzed_regions_count": len(result.analyzed_regions),
                "evidence_count": len(result.evidence),
                "observations_count": len(result.observations),
                "findings_count": len(result.findings),
            },
        )

    def _is_valid_bbox(
        self,
        bbox: List[float],
        max_dims: Optional[tuple] = None,
    ) -> bool:
        """Validate bounding box format: [x0, y0, x1, y1] with x0 <= x1 and y0 <= y1."""
        if not bbox or len(bbox) != 4:
            return False
        x0, y0, x1, y1 = bbox
        if x0 < 0 or y0 < 0:
            return False
        if x0 > x1 or y0 > y1:
            return False
        if max_dims:
            max_w, max_h = max_dims
            if x1 > max_w or y1 > max_h:
                return False
        return True

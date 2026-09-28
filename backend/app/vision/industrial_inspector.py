"""Industrial photograph inspection analyzer and candidate finding generator."""

import uuid
from typing import Dict, Any, List, Optional

from backend.app.vision.schemas import (
    EngineeringEvidence,
    EngineeringEvidenceType,
    VisualObservation,
    EngineeringFinding,
    ConfidenceAssessment,
    ConfidenceLevel,
)


class IndustrialPhotoInspector:
    """Analyzes industrial photographs and equipment images producing strictly non-certified candidate observations."""

    # Disallowed certified / conclusive diagnostic terms (must be downgraded)
    CERTIFIED_CLAIMS_MAP = {
        "is broken": "shows visible damage candidate",
        "is defective": "displays candidate irregularity requiring verification",
        "unsafe": "exhibits visual anomaly requiring physical safety evaluation",
        "failure confirmed": "visible candidate pattern observed; failure unverified",
        "corroded": "shows visible corrosion candidate",
        "cracked": "shows crack-like surface indication",
        "leaking": "displays candidate fluid/discoloration indication",
        "failed": "shows visual anomaly candidate",
    }

    REQUIRED_QUALIFIERS = [
        "candidate",
        "visible indication",
        "possible",
        "observed",
        "requires verification",
    ]

    def create_candidate_observation(
        self,
        region_id: str,
        observed_visual_features: str,
        inferred_interpretation: str,
        uncertainty_statement: str,
        confidence: ConfidenceAssessment,
        evidence_refs: Optional[List[str]] = None,
    ) -> VisualObservation:
        """Create a VisualObservation strictly separating observation, interpretation, and uncertainty."""
        # Sanitize interpretation to ensure candidate language
        clean_interpretation = self.sanitize_engineering_language(inferred_interpretation)

        return VisualObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:8]}",
            region_id=region_id,
            observation=observed_visual_features,
            interpretation=clean_interpretation,
            uncertainty=uncertainty_statement,
            confidence=confidence,
            evidence_refs=evidence_refs or [],
            verification_required=True,
            verification_status="PENDING_VERIFICATION",
        )

    def create_candidate_finding(
        self,
        title: str,
        description: str,
        finding_type: str,
        confidence: ConfidenceAssessment,
        evidence_ids: Optional[List[str]] = None,
        severity: str = "INFORMATIONAL",
    ) -> EngineeringFinding:
        """Create a candidate finding with mandatory verification recommendation."""
        clean_title = self.sanitize_engineering_language(title)
        clean_desc = self.sanitize_engineering_language(description)

        # Ensure title reflects candidate status
        if not any(q in clean_title.lower() for q in self.REQUIRED_QUALIFIERS):
            clean_title = f"Candidate {clean_title}"

        return EngineeringFinding(
            finding_id=f"find_{uuid.uuid4().hex[:8]}",
            title=clean_title,
            description=clean_desc,
            finding_type=finding_type,
            severity=severity,
            evidence_ids=evidence_ids or [],
            confidence=confidence,
            recommendation="Observations are visual candidates only; requires on-site qualified human engineering verification.",
        )

    def sanitize_engineering_language(self, text: str) -> str:
        """Replace definitive diagnostic claims with calibrated candidate observations."""
        sanitized = text
        for claim, replacement in self.CERTIFIED_CLAIMS_MAP.items():
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(claim), re.IGNORECASE)
            sanitized = pattern.sub(replacement, sanitized)

        # Enforce that no claim says "The equipment is unsafe" without qualification
        if "unsafe" in sanitized.lower() and "evaluation" not in sanitized.lower():
            sanitized += " (Note: Visual inspection cannot establish certified operational safety)."

        return sanitized

    def inspect_visual_anomalies(
        self,
        image_metadata: Dict[str, Any],
        detected_features: List[Dict[str, Any]],
        document_id: str,
        source_hash: str,
        page_number: int = 1,
    ) -> Tuple[List[EngineeringEvidence], List[VisualObservation], List[EngineeringFinding]]:
        """Process detected features into structured evidence, observations, and findings."""
        evidence_list: List[EngineeringEvidence] = []
        observations: List[VisualObservation] = []
        findings: List[EngineeringFinding] = []

        for feat in detected_features:
            region_id = feat.get("region_id", f"reg_{uuid.uuid4().hex[:6]}")
            feat_type = feat.get("type", "defect_candidate")
            bbox = feat.get("bounding_box", [0.0, 0.0, 0.0, 0.0])
            desc = feat.get("description", "Visible surface pattern observed")
            raw_obs = feat.get("observation", desc)
            raw_interp = feat.get("interpretation", "Potential surface anomaly candidate")
            raw_uncertainty = feat.get(
                "uncertainty",
                "2D visual imagery cannot determine surface depth, metallurgical composition, or internal integrity.",
            )
            score = feat.get("confidence", 0.65)

            conf = ConfidenceAssessment.from_score(
                score=score,
                rationale=feat.get("rationale", "Visual feature pattern identification"),
            )

            # 1. Create Evidence
            ev = EngineeringEvidence(
                evidence_id=f"ev_insp_{uuid.uuid4().hex[:8]}",
                document_id=document_id,
                source_hash=source_hash,
                page_number=page_number,
                region_id=region_id,
                evidence_type=EngineeringEvidenceType.DEFECT_CANDIDATE if "defect" in feat_type or "corrosion" in feat_type else EngineeringEvidenceType.PHOTOGRAPH,
                bounding_box=bbox,
                observation=raw_obs,
                extracted_text=feat.get("text", None),
                visual_features=feat,
                confidence=conf,
                extraction_method="industrial_visual_analyzer",
                source_reference=f"page_{page_number}_region_{region_id}",
            )
            evidence_list.append(ev)

            # 2. Create Observation
            obs = self.create_candidate_observation(
                region_id=region_id,
                observed_visual_features=raw_obs,
                inferred_interpretation=raw_interp,
                uncertainty_statement=raw_uncertainty,
                confidence=conf,
                evidence_refs=[ev.evidence_id],
            )
            observations.append(obs)

            # 3. Create Finding
            finding = self.create_candidate_finding(
                title=feat.get("title", f"{feat_type.replace('_', ' ').capitalize()} candidate"),
                description=obs.interpretation,
                finding_type=feat_type,
                confidence=conf,
                evidence_ids=[ev.evidence_id],
                severity=feat.get("severity", "MEDIUM"),
            )
            findings.append(finding)

        return evidence_list, observations, findings

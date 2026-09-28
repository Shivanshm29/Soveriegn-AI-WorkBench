"""Deterministic dimension, tolerance, and engineering annotation extractor."""

import re
import uuid
from typing import Dict, Any, List, Optional, Tuple

from backend.app.vision.schemas import (
    DimensionItem,
    EngineeringEvidence,
    EngineeringEvidenceType,
    ConfidenceAssessment,
    ConfidenceLevel,
)


class DimensionExtractor:
    """Extracts and normalizes engineering dimensions, tolerances, and units without hallucination."""

    # Common engineering prefixes
    DIAMETER_PREFIX = re.compile(r"(?:[Øø⌀]|DIA\.?|DIAMETER)\s*", re.IGNORECASE)
    RADIUS_PREFIX = re.compile(r"(?:[Rr]|RAD\.?|RADIUS)\s*", re.IGNORECASE)
    THREAD_PREFIX = re.compile(r"^[Mm](\d+(?:\.\d+)?)(?:[xX](\d+(?:\.\d+)?))?", re.IGNORECASE)
    QUANTITY_PREFIX = re.compile(r"^(\d+)\s*[xX]\s*", re.IGNORECASE)

    # Tolerances
    SYMMETRIC_TOL = re.compile(r"(?:±|\+\/\-)\s*(\d+(?:\.\d+)?)")
    BILATERAL_TOL = re.compile(r"\+(\d+(?:\.\d+)?)\s*(?:\/|\s)\s*\-(\d+(?:\.\d+)?)")
    FIT_CLASS_TOL = re.compile(r"\b([A-Za-z]{1,2}\d{1,2})\b")

    # Units
    UNITS_PATTERN = re.compile(r"\b(mm|cm|m|in|inch|inches|ft|deg|degrees|rad|°)\b", re.IGNORECASE)

    # Approximate / ambiguous markers (must trigger value=None and low confidence)
    AMBIGUOUS_MARKERS = re.compile(
        r"(?:approx|approximately|looks\s+like|estimated|about|~|\?|unclear|blurred)",
        re.IGNORECASE,
    )

    def extract_from_text(
        self,
        text: str,
        bounding_box: Optional[List[float]] = None,
        base_confidence: float = 0.9,
    ) -> List[DimensionItem]:
        """Parse raw text string or annotation block into structured DimensionItems."""
        if not text or not text.strip():
            return []

        bbox = bounding_box or [0.0, 0.0, 0.0, 0.0]
        items: List[DimensionItem] = []

        # Split on line breaks or commas/semicolons
        lines = [line.strip() for line in re.split(r"[\n;\r]+", text) if line.strip()]

        for line in lines:
            parsed = self._parse_single_dimension(line, bbox, base_confidence)
            if parsed:
                items.append(parsed)

        return items

    def _parse_single_dimension(
        self,
        raw_text: str,
        bounding_box: List[float],
        base_confidence: float,
    ) -> Optional[DimensionItem]:
        """Parse a single potential dimension line adhering strictly to Section 9 rules."""
        raw = raw_text.strip()
        if not raw:
            return None

        # Check for ambiguity markers first
        if self.AMBIGUOUS_MARKERS.search(raw):
            return DimensionItem(
                dimension_id=f"dim_{uuid.uuid4().hex[:8]}",
                raw_text=raw,
                value=None,  # Section 9: If system cannot confidently read: value = None
                unit=None,
                tolerance=None,
                feature_type="ambiguous_indication",
                bounding_box=bounding_box,
                confidence=ConfidenceAssessment(
                    value=0.2,
                    level=ConfidenceLevel.LOW,
                    rationale="Ambiguous or approximate dimension indicator; value not certifiably readable.",
                ),
                uncertainty="Value contains approximate or unreadable qualifiers; cannot establish nominal dimension.",
            )

        # Detect feature prefix
        feature_type = "linear"
        clean_text = raw
        multiplier = 1

        qty_match = self.QUANTITY_PREFIX.match(clean_text)
        if qty_match:
            try:
                multiplier = int(qty_match.group(1))
            except ValueError:
                multiplier = 1
            clean_text = clean_text[qty_match.end() :].strip()

        if self.DIAMETER_PREFIX.match(clean_text):
            feature_type = "diameter"
            clean_text = self.DIAMETER_PREFIX.sub("", clean_text).strip()
        elif self.RADIUS_PREFIX.match(clean_text):
            feature_type = "radius"
            clean_text = self.RADIUS_PREFIX.sub("", clean_text).strip()
        elif self.THREAD_PREFIX.match(clean_text):
            feature_type = "thread"

        # Check for angular indication
        if "°" in clean_text or re.search(r"\b(?:deg|degrees)\b", clean_text, re.IGNORECASE):
            feature_type = "angular"

        # Detect unit
        unit: Optional[str] = None
        unit_match = self.UNITS_PATTERN.search(clean_text)
        if unit_match:
            unit = unit_match.group(1).lower()
            if unit in ["degrees", "deg"]:
                unit = "°"

        # Detect tolerances
        tolerance: Optional[str] = None
        sym_match = self.SYMMETRIC_TOL.search(clean_text)
        if sym_match:
            tolerance = f"±{sym_match.group(1)}"
        else:
            bilat_match = self.BILATERAL_TOL.search(clean_text)
            if bilat_match:
                tolerance = f"+{bilat_match.group(1)}/-{bilat_match.group(2)}"
            else:
                fit_match = self.FIT_CLASS_TOL.search(clean_text)
                if fit_match and fit_match.group(1).upper() not in ["MM", "CM", "IN"]:
                    tolerance = fit_match.group(1)

        # Extract nominal numeric value
        # Look for leading float/int in cleaned string
        num_match = re.search(r"[-+]?\d*\.?\d+", clean_text)
        if not num_match:
            # Not a numeric dimension, could be a general annotation
            return None

        try:
            nominal_val = float(num_match.group(0))
        except ValueError:
            return DimensionItem(
                dimension_id=f"dim_{uuid.uuid4().hex[:8]}",
                raw_text=raw,
                value=None,
                unit=unit,
                tolerance=tolerance,
                feature_type=feature_type,
                bounding_box=bounding_box,
                confidence=ConfidenceAssessment(
                    value=0.1,
                    level=ConfidenceLevel.UNKNOWN,
                    rationale="Failed to parse numeric value from token.",
                ),
                uncertainty="Numeric token could not be converted to floating point value.",
            )

        # Compute confidence
        score = base_confidence
        rationale_parts = ["Direct deterministic regex match"]
        if tolerance:
            rationale_parts.append(f"tolerance identified ({tolerance})")
        if unit:
            rationale_parts.append(f"unit identified ({unit})")
        if multiplier > 1:
            rationale_parts.append(f"quantity count ({multiplier}x)")

        return DimensionItem(
            dimension_id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=raw,
            value=nominal_val,
            unit=unit or "mm",  # Default engineering unit standard if not specified
            tolerance=tolerance,
            feature_type=feature_type,
            bounding_box=bounding_box,
            confidence=ConfidenceAssessment.from_score(
                score=score,
                rationale="; ".join(rationale_parts),
            ),
            uncertainty=None if (unit and tolerance) else "Implicit unit or tolerance may rely on general drawing notes.",
        )

    def to_engineering_evidence(
        self,
        dimensions: List[DimensionItem],
        document_id: str,
        source_hash: str,
        page_number: int,
        region_id: str,
    ) -> List[EngineeringEvidence]:
        """Convert DimensionItems to auditable EngineeringEvidence objects."""
        evidence_list: List[EngineeringEvidence] = []
        for dim in dimensions:
            desc = f"Extracted dimension: {dim.raw_text}"
            if dim.value is not None:
                desc += f" (nominal: {dim.value} {dim.unit or ''}"
                if dim.tolerance:
                    desc += f" {dim.tolerance}"
                desc += ")"
            else:
                desc += " (nominal value unverified/unreadable)"

            evidence = EngineeringEvidence(
                evidence_id=f"ev_dim_{uuid.uuid4().hex[:8]}",
                document_id=document_id,
                source_hash=source_hash,
                page_number=page_number,
                region_id=region_id,
                evidence_type=EngineeringEvidenceType.DIMENSION,
                bounding_box=dim.bounding_box or [0.0, 0.0, 0.0, 0.0],
                observation=desc,
                extracted_text=dim.raw_text,
                visual_features={
                    "dimension_id": dim.dimension_id,
                    "value": dim.value,
                    "unit": dim.unit,
                    "tolerance": dim.tolerance,
                    "feature_type": dim.feature_type,
                },
                confidence=dim.confidence,
                extraction_method="deterministic_dimension_extractor",
                source_reference=f"page_{page_number}_region_{region_id}",
                metadata={"uncertainty": dim.uncertainty} if dim.uncertainty else {},
            )
            evidence_list.append(evidence)

        return evidence_list

"""Pydantic schemas and contracts for engineering drawing and industrial vision analysis."""

import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class EngineeringEvidenceType(str, Enum):
    """Specific categories of engineering and visual industrial evidence."""

    DIMENSION = "dimension"
    ANNOTATION = "annotation"
    SYMBOL = "symbol"
    COMPONENT = "component"
    LABEL = "label"
    TABLE = "table"
    DRAWING_VIEW = "drawing_view"
    TITLE_BLOCK = "title_block"
    PHOTOGRAPH = "photograph"
    DEFECT_CANDIDATE = "defect_candidate"
    GEOMETRIC_FEATURE = "geometric_feature"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Discrete confidence tiers for visual observations and findings."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ConfidenceAssessment(BaseModel):
    """Structured confidence representation with numeric score, categorical level, and rationale."""

    value: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    rationale: str

    @classmethod
    def from_score(cls, score: float, rationale: str = "") -> "ConfidenceAssessment":
        """Compute level from continuous score."""
        score = max(0.0, min(1.0, score))
        if score >= 0.80:
            level = ConfidenceLevel.HIGH
        elif score >= 0.50:
            level = ConfidenceLevel.MEDIUM
        elif score > 0.0:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.UNKNOWN
        return cls(value=round(score, 3), level=level, rationale=rationale or f"Computed from score {score:.2f}")


class DimensionItem(BaseModel):
    """Extracted dimensional specification preserving nominal value, unit, and tolerance."""

    dimension_id: str = Field(default_factory=lambda: f"dim_{uuid.uuid4().hex[:8]}")
    raw_text: str
    value: Optional[float] = None
    unit: Optional[str] = None
    tolerance: Optional[str] = None
    feature_type: Optional[str] = None  # diameter, radius, linear, angular
    bounding_box: List[float] = Field(default_factory=list)  # [x0, y0, x1, y1]
    confidence: ConfidenceAssessment
    uncertainty: Optional[str] = None


class VisualRegion(BaseModel):
    """Identified structural region within an engineering drawing or inspection image."""

    region_id: str = Field(default_factory=lambda: f"reg_{uuid.uuid4().hex[:8]}")
    page_number: int = 1
    region_type: str  # title_block, drawing_body, dimensions, annotations, symbols, tables, notes, labels, legends, views, sections, callouts, photographs, diagrams, unknown
    bounding_box: List[float]  # [x0, y0, x1, y1]
    confidence: ConfidenceAssessment
    source_hash: str = ""
    text_content: Optional[str] = None
    sub_elements: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImageTile(BaseModel):
    """Metadata representing a high-resolution sub-region/tile of a large drawing."""

    tile_id: str = Field(default_factory=lambda: f"tile_{uuid.uuid4().hex[:8]}")
    document_id: str
    source_hash: str
    page_number: int = 1
    bounding_box: List[float]  # [x0, y0, x1, y1] in original image coordinates
    original_dimensions: Tuple[int, int]
    tile_path: str
    tile_col: int
    tile_row: int
    preprocessing_metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineeringEvidence(BaseModel):
    """Primary evidence object linking visual features directly to document regions."""

    evidence_id: str = Field(default_factory=lambda: f"ev_eng_{uuid.uuid4().hex[:8]}")
    document_id: str
    source_hash: str
    page_number: int = 1
    region_id: str
    evidence_type: EngineeringEvidenceType
    bounding_box: List[float]  # [x0, y0, x1, y1]
    observation: str
    extracted_text: Optional[str] = None
    visual_features: Dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceAssessment
    extraction_method: str = "vision_engine"
    source_reference: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisualObservation(BaseModel):
    """Separates what was visually observed from what the model inferred and what remains uncertain."""

    observation_id: str = Field(default_factory=lambda: f"obs_{uuid.uuid4().hex[:8]}")
    region_id: str
    observation: str  # What was visually observed directly
    interpretation: str  # What the model inferred/hypothesized
    uncertainty: str  # Explicit statement of what remains uncertain
    confidence: ConfidenceAssessment
    evidence_refs: List[str] = Field(default_factory=list)  # Linked EngineeringEvidence IDs
    verification_required: bool = True
    verification_status: str = "PENDING_VERIFICATION"
    candidate_observation: bool = True


class EngineeringFinding(BaseModel):
    """High-level finding produced from analyzed observations and evidence."""

    finding_id: str = Field(default_factory=lambda: f"find_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    finding_type: str  # e.g., corrosion_candidate, surface_anomaly_candidate, dimension_indication
    severity: str = "INFORMATIONAL"  # INFORMATIONAL, LOW, MEDIUM, HIGH
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: ConfidenceAssessment
    recommendation: str = "Requires qualified human inspection and verification."


class EngineeringVisionResult(BaseModel):
    """Complete, auditable structured result of engineering drawing or industrial vision analysis."""

    task_id: str
    document_id: str
    source_hash: str
    analyzed_regions: List[VisualRegion] = Field(default_factory=list)
    evidence: List[EngineeringEvidence] = Field(default_factory=list)
    observations: List[VisualObservation] = Field(default_factory=list)
    findings: List[EngineeringFinding] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    verification_required: bool = True
    verification_status: str = "PENDING_VERIFICATION"
    verification_summary: str = ""
    model_used: str = "local_vision_model"
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)

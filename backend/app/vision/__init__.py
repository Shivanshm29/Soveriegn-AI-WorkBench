"""Phase 7 Engineering Drawing & Industrial Vision Agent Package."""

from backend.app.vision.schemas import (
    EngineeringEvidenceType,
    ConfidenceLevel,
    ConfidenceAssessment,
    DimensionItem,
    VisualRegion,
    ImageTile,
    EngineeringEvidence,
    VisualObservation,
    EngineeringFinding,
    EngineeringVisionResult,
)
from backend.app.vision.errors import (
    VisionProcessingError,
    CorruptImageError,
    OversizedImageError,
    TileGenerationError,
    RegionDetectionError,
    VisualVerificationError,
    VisionResourceLimitError,
    InvalidBoundingBoxError,
    MissingEvidenceError,
)
from backend.app.vision.preprocessing import ImagePreprocessor
from backend.app.vision.region_detector import VisualRegionDetector
from backend.app.vision.dimension_extractor import DimensionExtractor
from backend.app.vision.industrial_inspector import IndustrialPhotoInspector
from backend.app.vision.verifier import VisualEvidenceVerifier, VerificationReport
from backend.app.vision.agent import EngineeringVisionAgent
from backend.app.vision.tools import get_vision_tools, register_vision_tools

__all__ = [
    "EngineeringEvidenceType",
    "ConfidenceLevel",
    "ConfidenceAssessment",
    "DimensionItem",
    "VisualRegion",
    "ImageTile",
    "EngineeringEvidence",
    "VisualObservation",
    "EngineeringFinding",
    "EngineeringVisionResult",
    "VisionProcessingError",
    "CorruptImageError",
    "OversizedImageError",
    "TileGenerationError",
    "RegionDetectionError",
    "VisualVerificationError",
    "VisionResourceLimitError",
    "InvalidBoundingBoxError",
    "MissingEvidenceError",
    "ImagePreprocessor",
    "VisualRegionDetector",
    "DimensionExtractor",
    "IndustrialPhotoInspector",
    "VisualEvidenceVerifier",
    "VerificationReport",
    "EngineeringVisionAgent",
    "get_vision_tools",
    "register_vision_tools",
]

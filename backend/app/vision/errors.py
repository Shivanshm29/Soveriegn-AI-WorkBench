"""Structured exceptions for engineering drawing and industrial vision analysis."""

from typing import Optional, Dict, Any


class VisionProcessingError(Exception):
    """Base class for all vision processing exceptions."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CorruptImageError(VisionProcessingError):
    """Raised when an image file is corrupted or truncated."""
    pass


class UnsupportedImageFormatError(VisionProcessingError):
    """Raised when an image format is unsupported."""
    pass


class OversizedImageError(VisionProcessingError):
    """Raised when image resolution or file size exceeds maximum limits."""

    def __init__(self, message: str, width: int, height: int, max_dim: int):
        super().__init__(message, details={"width": width, "height": height, "max_dim": max_dim})
        self.width = width
        self.height = height
        self.max_dim = max_dim


class TileGenerationError(VisionProcessingError):
    """Raised when tiling a large drawing fails."""

    def __init__(
        self,
        message: str,
        requested_tiles: Optional[int] = None,
        max_tiles: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        d = dict(details or {})
        if requested_tiles is not None:
            d["requested_tiles"] = requested_tiles
        if max_tiles is not None:
            d["max_tiles"] = max_tiles
        super().__init__(message, details=d)
        self.requested_tiles = requested_tiles
        self.max_tiles = max_tiles


class RegionDetectionError(VisionProcessingError):
    """Raised when region extraction fails."""
    pass


class VisualVerificationError(VisionProcessingError):
    """Raised when deterministic verification fails."""
    pass


class VisionResourceLimitError(VisionProcessingError):
    """Raised when maximum VLM calls, tiles, or processing time limits are breached."""
    pass


class VisionTimeoutError(VisionProcessingError):
    """Raised when a vision processing step times out."""
    pass


class InvalidBoundingBoxError(VisionProcessingError):
    """Raised when a bounding box is invalid or out of image coordinates."""
    pass


class MissingEvidenceError(VisionProcessingError):
    """Raised when an observation references an evidence ID that does not exist."""
    pass


class MalformedModelOutputError(VisionProcessingError):
    """Raised when the vision model produces output that violates the expected schema."""
    pass

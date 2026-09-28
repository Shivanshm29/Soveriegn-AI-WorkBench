"""Structured models and contracts for multimodal document processing."""

import os
import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Recognized document structural categories."""

    TEXT_PDF = "TEXT_PDF"
    SCANNED_PDF = "SCANNED_PDF"
    IMAGE_PDF = "IMAGE_PDF"
    IMAGE = "IMAGE"
    UNSUPPORTED = "UNSUPPORTED"


class EvidenceType(str, Enum):
    """Categories of multimodal normalized evidence."""

    TEXT = "TEXT"
    OCR_TEXT = "OCR_TEXT"
    TABLE = "TABLE"
    IMAGE = "IMAGE"
    FIGURE = "FIGURE"
    HANDWRITING = "HANDWRITING"
    VLM_OBSERVATION = "VLM_OBSERVATION"
    LAYOUT_REGION = "LAYOUT_REGION"


class DocumentInput(BaseModel):
    """Structured ingestion contract representing an input document."""

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_path: str
    filename: str
    mime_type: str
    file_size: int
    source_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> "DocumentInput":
        """Construct DocumentInput by inspecting local file and computing SHA-256."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source document not found: {file_path}")

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        source_hash = hasher.hexdigest()

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Fallback based on extension
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".pdf":
                mime_type = "application/pdf"
            elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
                mime_type = f"image/{ext.replace('.', '')}"
            else:
                mime_type = "application/octet-stream"

        return cls(
            source_path=os.path.abspath(file_path),
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            source_hash=source_hash,
            metadata=metadata or {},
        )


class DocumentTypeResult(BaseModel):
    """Structured result of document type inspection."""

    document_id: str
    detected_type: DocumentType
    page_count: int
    has_extractable_text: bool
    has_images: bool
    detection_method: str
    confidence: float = 1.0
    details: Dict[str, Any] = Field(default_factory=dict)


class RenderedPage(BaseModel):
    """Metadata representing a locally rendered document page image."""

    document_id: str
    source_hash: str
    page_number: int
    width: int
    height: int
    image_path: str
    format: str = "png"
    dpi: int = 150


class OCRBlock(BaseModel):
    """Normalized OCR text block with spatial coordinates and confidence."""

    block_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_number: int
    text: str
    confidence: float
    bounding_box: List[float]  # [x0, y0, x1, y1]
    source_hash: str
    extraction_method: str = "native_text"  # native_text, paddleocr, tesseract, vlm


class LayoutRegion(BaseModel):
    """Identified structural region within a document page."""

    region_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_number: int
    region_type: str  # paragraph, heading, table, figure, image, caption, list, handwritten_region, unknown_region
    bounding_box: List[float]  # [x0, y0, x1, y1]
    confidence: float = 1.0
    content: Optional[str] = None
    source_hash: str = ""


class TableBlock(BaseModel):
    """Extracted table representation preserving page, coordinates, and cell data."""

    table_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_number: int
    bounding_box: List[float]  # [x0, y0, x1, y1]
    rows: List[List[str]] = Field(default_factory=list)
    headers: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    source_hash: str = ""


class ImageBlock(BaseModel):
    """Extracted embedded image or figure region within a document."""

    image_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_number: int
    bounding_box: List[float]  # [x0, y0, x1, y1]
    source_hash: str
    image_reference: str  # local filepath or reference key
    extraction_method: str = "pymupdf"
    confidence: float = 1.0


class DocumentEvidence(BaseModel):
    """Normalized evidence item traceable to document, page, and coordinates."""

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    source_hash: str
    page_number: int
    evidence_type: EvidenceType
    text: Optional[str] = None
    bounding_box: Optional[List[float]] = None
    confidence: Optional[float] = None
    extraction_method: str
    source_reference: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentAnalysisResult(BaseModel):
    """Comprehensive serializable outcome of multimodal document analysis."""

    document_id: str
    source_hash: str
    document_type: DocumentType
    page_count: int
    evidence: List[DocumentEvidence] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence_summary: Dict[str, Any] = Field(default_factory=dict)

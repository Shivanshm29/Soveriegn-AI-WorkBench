"""Multimodal document understanding pipeline package."""

from backend.app.multimodal.schemas import (
    DocumentType,
    EvidenceType,
    DocumentInput,
    DocumentTypeResult,
    RenderedPage,
    OCRBlock,
    LayoutRegion,
    TableBlock,
    ImageBlock,
    DocumentEvidence,
    DocumentAnalysisResult,
)
from backend.app.multimodal.errors import (
    DocumentProcessingError,
    UnsupportedDocumentError,
    InvalidPDFError,
    UnreadablePageError,
    OCRError,
    RenderingError,
    VLMError,
    ExtractionError,
    DocumentTooLargeError,
    PageLimitExceededError,
    ResourceLimitError,
)
from backend.app.multimodal.type_detector import DocumentTypeDetector
from backend.app.multimodal.pdf_processor import PDFProcessor
from backend.app.multimodal.ocr_engine import LocalOCREngine
from backend.app.multimodal.layout_analyzer import LayoutAnalyzer
from backend.app.multimodal.vlm_adapter import VLMDocumentAdapter
from backend.app.multimodal.prompt_defense import PromptInjectionDefense
from backend.app.multimodal.cache import DocumentCache
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.multimodal.tools import get_multimodal_tools, register_multimodal_tools

__all__ = [
    "DocumentType",
    "EvidenceType",
    "DocumentInput",
    "DocumentTypeResult",
    "RenderedPage",
    "OCRBlock",
    "LayoutRegion",
    "TableBlock",
    "ImageBlock",
    "DocumentEvidence",
    "DocumentAnalysisResult",
    "DocumentProcessingError",
    "UnsupportedDocumentError",
    "InvalidPDFError",
    "UnreadablePageError",
    "OCRError",
    "RenderingError",
    "VLMError",
    "ExtractionError",
    "DocumentTooLargeError",
    "PageLimitExceededError",
    "ResourceLimitError",
    "DocumentTypeDetector",
    "PDFProcessor",
    "LocalOCREngine",
    "LayoutAnalyzer",
    "VLMDocumentAdapter",
    "PromptInjectionDefense",
    "DocumentCache",
    "MultimodalDocumentPipeline",
    "get_multimodal_tools",
    "register_multimodal_tools",
]

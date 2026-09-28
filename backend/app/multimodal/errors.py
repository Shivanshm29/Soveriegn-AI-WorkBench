"""Structured exceptions for multimodal document processing."""

from typing import Optional, Dict, Any


class DocumentProcessingError(Exception):
    """Base class for all multimodal document processing errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedDocumentError(DocumentProcessingError):
    """Raised when an ingested file has an unrecognized or unsupported structure."""
    pass


class InvalidPDFError(DocumentProcessingError):
    """Raised when a PDF file is corrupt, malformed, or cannot be parsed."""
    pass


class UnreadablePageError(DocumentProcessingError):
    """Raised when a specific page inside a document cannot be accessed or decoded."""

    def __init__(self, message: str, page_number: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.page_number = page_number


class OCRError(DocumentProcessingError):
    """Raised when local OCR fails during text recognition on a rendered page or image."""

    def __init__(self, message: str, page_number: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.page_number = page_number


class RenderingError(DocumentProcessingError):
    """Raised when local page rasterization/rendering fails."""

    def __init__(self, message: str, page_number: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.page_number = page_number


class VLMError(DocumentProcessingError):
    """Raised when local Vision-Language Model inference fails."""
    pass


class ExtractionError(DocumentProcessingError):
    """Raised when table, image, or structural extraction fails."""
    pass


class DocumentTooLargeError(DocumentProcessingError):
    """Raised when document size exceeds the configured safe local limit."""

    def __init__(self, message: str, file_size: int, max_allowed: int):
        super().__init__(message, details={"file_size": file_size, "max_allowed": max_allowed})
        self.file_size = file_size
        self.max_allowed = max_allowed


class PageLimitExceededError(DocumentProcessingError):
    """Raised when document page count exceeds the configured safe local limit."""

    def __init__(self, message: str, page_count: int, max_allowed: int):
        super().__init__(message, details={"page_count": page_count, "max_allowed": max_allowed})
        self.page_count = page_count
        self.max_allowed = max_allowed


class ResourceLimitError(DocumentProcessingError):
    """Raised when local memory, timeout, or temporary storage limits are breached."""
    pass

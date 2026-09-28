"""Structured exceptions for Phase 8 Local Hybrid RAG & Sovereign Knowledge Agent."""

from typing import Optional, Dict, Any


class RAGError(Exception):
    """Base class for all RAG-related exceptions."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VectorStoreUnavailableError(RAGError):
    """Raised when Qdrant is not reachable or returns an error."""
    pass


class EmbeddingUnavailableError(RAGError):
    """Raised when the local embedding model is not reachable or fails."""
    pass


class EmbeddingDimensionMismatchError(RAGError):
    """Raised when embedding dimensions do not match the Qdrant collection."""
    pass


class LexicalIndexUnavailableError(RAGError):
    """Raised when the BM25 index is missing or corrupted."""
    pass


class IngestionError(RAGError):
    """Raised when document ingestion fails."""
    pass


class RetrievalError(RAGError):
    """Raised when hybrid retrieval fails."""
    pass


class UnauthorizedRetrievalError(RAGError):
    """Raised when a retrieval request is blocked by sensitivity/policy controls."""
    pass


class CitationVerificationError(RAGError):
    """Raised when a generated citation cannot be verified against retrieved evidence."""
    pass


class ResourceLimitExceededError(RAGError):
    """Raised when ingestion or retrieval exceeds configured resource limits."""
    pass


class StaleIndexError(RAGError):
    """Raised when stale (hash-mismatched) chunks are detected in the index."""
    pass


class UnsupportedFormatError(RAGError):
    """Raised when a document format is not supported by the ingestion pipeline."""
    pass


class GroundedGenerationError(RAGError):
    """Raised when grounded generation fails or produces malformed output."""
    pass

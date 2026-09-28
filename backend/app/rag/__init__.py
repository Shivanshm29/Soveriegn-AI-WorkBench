"""Phase 8 — Local Hybrid RAG & Sovereign Knowledge Agent."""

from backend.app.rag.schemas import (
    KnowledgeSource,
    KnowledgeChunk,
    IndexManifest,
    RetrievalResult,
    EvidencePack,
    GroundedAnswer,
    CitationRef,
    QueryAnalysis,
    IngestionStatus,
    ChunkingVersion,
    RAGVerificationReport,
)
from backend.app.rag.errors import (
    RAGError,
    VectorStoreUnavailableError,
    EmbeddingUnavailableError,
    EmbeddingDimensionMismatchError,
    LexicalIndexUnavailableError,
    IngestionError,
    RetrievalError,
    UnauthorizedRetrievalError,
    CitationVerificationError,
    ResourceLimitExceededError,
    StaleIndexError,
    UnsupportedFormatError,
)

__all__ = [
    "KnowledgeSource", "KnowledgeChunk", "IndexManifest",
    "RetrievalResult", "EvidencePack", "GroundedAnswer", "CitationRef",
    "QueryAnalysis", "IngestionStatus", "ChunkingVersion", "RAGVerificationReport",
    "RAGError", "VectorStoreUnavailableError", "EmbeddingUnavailableError",
    "EmbeddingDimensionMismatchError", "LexicalIndexUnavailableError",
    "IngestionError", "RetrievalError", "UnauthorizedRetrievalError",
    "CitationVerificationError", "ResourceLimitExceededError",
    "StaleIndexError", "UnsupportedFormatError",
]

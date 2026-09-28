"""Pydantic schemas for Phase 8 Local Hybrid RAG & Sovereign Knowledge Agent."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNKING_VERSION = "1.0"
INDEX_VERSION = "1.0"


class ChunkingVersion(str, Enum):
    V1 = "1.0"


# ---------------------------------------------------------------------------
# Knowledge Source
# ---------------------------------------------------------------------------

class KnowledgeSource(BaseModel):
    """Represents a document being ingested into the knowledge base."""

    document_id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    source_path: str
    filename: str
    document_type: str = "unknown"  # pdf, txt, md, docx, csv, xlsx, image, evidence
    source_hash: str = ""
    file_size: int = 0
    sensitivity: str = "INTERNAL"  # PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Knowledge Chunk
# ---------------------------------------------------------------------------

class KnowledgeChunk(BaseModel):
    """A single indexed unit of knowledge with full provenance metadata."""

    chunk_id: str = Field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:12]}")
    document_id: str
    source_hash: str
    filename: str = ""
    source_path: str = ""
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    chunk_index: int = 0
    char_offset_start: Optional[int] = None
    char_offset_end: Optional[int] = None
    document_type: str = "text"
    sensitivity: str = "INTERNAL"
    extraction_method: str = "text_splitter"
    chunking_version: str = CHUNKING_VERSION
    embedding_model: str = ""
    index_version: str = INDEX_VERSION
    table_headers: Optional[List[str]] = None
    table_rows: Optional[List[List[str]]] = None
    is_table: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def vector_id(self) -> str:
        """Deterministic vector store ID keyed by content identity."""
        return f"{self.source_hash[:16]}_{self.chunk_index}"


# ---------------------------------------------------------------------------
# Index Manifest
# ---------------------------------------------------------------------------

class IngestionStatus(str, Enum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    STALE = "STALE"
    DELETED = "DELETED"


class IndexManifest(BaseModel):
    """Auditable record of an indexed document in the knowledge base."""

    document_id: str
    source_hash: str
    filename: str
    source_path: str
    chunk_count: int = 0
    embedding_model: str = ""
    embedding_dimension: int = 0
    chunking_version: str = CHUNKING_VERSION
    index_version: str = INDEX_VERSION
    sensitivity: str = "INTERNAL"
    document_type: str = "unknown"
    status: IngestionStatus = IngestionStatus.PENDING
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Retrieval Result
# ---------------------------------------------------------------------------

class RetrievalResult(BaseModel):
    """A single retrieved chunk with full ranking metadata."""

    result_id: str = Field(default_factory=lambda: f"ret_{uuid.uuid4().hex[:8]}")
    document_id: str
    chunk_id: str
    source_hash: str
    filename: str = ""
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    dense_score: float = 0.0
    lexical_score: float = 0.0
    dense_rank: int = 0
    lexical_rank: int = 0
    fusion_score: float = 0.0
    sensitivity: str = "INTERNAL"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_table: bool = False
    table_headers: Optional[List[str]] = None
    table_rows: Optional[List[List[str]]] = None


# ---------------------------------------------------------------------------
# Evidence Pack
# ---------------------------------------------------------------------------

class EvidencePack(BaseModel):
    """Structured evidence container passed to the local LLM for grounded generation."""

    pack_id: str = Field(default_factory=lambda: f"pack_{uuid.uuid4().hex[:8]}")
    query: str
    results: List[RetrievalResult] = Field(default_factory=list)
    total_retrieved: int = 0
    evidence_token_estimate: int = 0
    query_analysis: Optional[Dict[str, Any]] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Citation and Grounded Answer
# ---------------------------------------------------------------------------

class CitationRef(BaseModel):
    """A single citation linking a claim to a source."""

    citation_id: str = Field(default_factory=lambda: f"cit_{uuid.uuid4().hex[:8]}")
    result_id: str
    chunk_id: str
    document_id: str
    source_hash: str
    filename: str = ""
    page_number: Optional[int] = None
    section: Optional[str] = None
    label: str = ""  # e.g. "[DOC-1, p.4, chunk-12]"


class GroundedAnswer(BaseModel):
    """A verified, grounded answer from the local LLM."""

    answer_id: str = Field(default_factory=lambda: f"ans_{uuid.uuid4().hex[:8]}")
    query: str
    answer: str
    citations: List[CitationRef] = Field(default_factory=list)
    evidence_pack_id: str = ""
    insufficient_evidence: bool = False
    verification_passed: bool = False
    verification_errors: List[str] = Field(default_factory=list)
    model_used: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Query Analysis
# ---------------------------------------------------------------------------

class QueryAnalysis(BaseModel):
    """Deterministic query analysis for hybrid retrieval."""

    original_query: str
    normalized_query: str = ""
    keywords: List[str] = Field(default_factory=list)
    exact_identifiers: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    sensitivity_scope: str = "INTERNAL"  # max sensitivity level to retrieve


# ---------------------------------------------------------------------------
# RAG Verification Report
# ---------------------------------------------------------------------------

class RAGVerificationReport(BaseModel):
    """Deterministic verification result for a GroundedAnswer."""

    is_valid: bool
    status: str  # "VERIFIED", "VERIFICATION_FAILED", "INSUFFICIENT_EVIDENCE"
    total_checks: int
    passed_checks: int
    failed_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

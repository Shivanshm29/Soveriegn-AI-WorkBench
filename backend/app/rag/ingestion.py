"""Knowledge ingestion pipeline for Phase 8 RAG - reuses Phase 6 document extraction."""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.rag.schemas import (
    IndexManifest,
    IngestionStatus,
    KnowledgeChunk,
    KnowledgeSource,
    CHUNKING_VERSION,
    INDEX_VERSION,
)
from backend.app.rag.errors import (
    IngestionError,
    ResourceLimitExceededError,
    StaleIndexError,
    UnsupportedFormatError,
)
from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.embedder import LocalEmbedder
from backend.app.rag.vector_store import VectorStore
from backend.app.rag.lexical_index import LexicalIndex
from backend.app.rag.manifest import ManifestStore
from backend.app.multimodal.prompt_defense import PromptInjectionDefense
from backend.app.security.data_sensitivity import DataSensitivity, parse_data_sensitivity

logger = logging.getLogger("app.rag.ingestion")

# Supported extensions
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv"}
SUPPORTED_PDF_EXTENSION = ".pdf"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGES = 100


def _compute_source_hash(path: str) -> str:
    """Compute SHA-256 hash of a file's binary content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of a text string."""
    return hashlib.sha256(text.encode("utf-8")).digest().hex()


class KnowledgeIngestionPipeline:
    """
    Sovereign, local knowledge ingestion pipeline.

    Reuses Phase 6 PDFProcessor for PDF extraction.
    All operations are local; no cloud services permitted.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        lexical_index: LexicalIndex,
        embedder: LocalEmbedder,
        manifest_store: ManifestStore,
        chunker: Optional[DocumentChunker] = None,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
        max_pages: int = MAX_PAGES,
    ):
        self.vector_store = vector_store
        self.lexical_index = lexical_index
        self.embedder = embedder
        self.manifest_store = manifest_store
        self.chunker = chunker or DocumentChunker()
        self.max_file_size = max_file_size
        self.max_pages = max_pages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_text(
        self,
        text: str,
        document_id: str,
        filename: str = "inline_text",
        sensitivity: str = "INTERNAL",
        metadata: Optional[Dict[str, Any]] = None,
        force_reindex: bool = False,
    ) -> IndexManifest:
        """Ingest raw text directly (e.g., from engineering evidence or test fixtures)."""
        source_hash = _compute_text_hash(text)
        return self._run_ingestion(
            document_id=document_id,
            source_hash=source_hash,
            source_path=filename,
            filename=filename,
            text=text,
            sensitivity=sensitivity,
            document_type="text",
            metadata=metadata or {},
            force_reindex=force_reindex,
        )

    def ingest_file(
        self,
        source: KnowledgeSource,
        force_reindex: bool = False,
    ) -> IndexManifest:
        """Ingest a file from disk into the knowledge base."""
        path = source.source_path
        if not os.path.exists(path):
            raise IngestionError(
                f"Source file not found: {path}",
                details={"document_id": source.document_id},
            )

        # Resource limit: file size
        fsize = os.path.getsize(path)
        if fsize > self.max_file_size:
            raise ResourceLimitExceededError(
                f"File too large: {fsize} bytes (limit {self.max_file_size}).",
                details={"path": path, "size": fsize},
            )

        source.file_size = fsize
        ext = os.path.splitext(path)[1].lower()

        # Compute source hash
        source_hash = _compute_source_hash(path)
        source.source_hash = source_hash

        # Hash-change detection
        if not force_reindex and self.manifest_store.detect_hash_change(source.document_id, source_hash):
            # Stale: remove old index entries, then re-index
            logger.info(
                "Detected hash change for document_id=%s — removing stale index entries.",
                source.document_id,
            )
            self._remove_document(source.document_id)

        # Extract text from file
        try:
            text, doc_type = self._extract_text(path, ext)
        except UnsupportedFormatError:
            manifest = IndexManifest(
                document_id=source.document_id,
                source_hash=source_hash,
                filename=source.filename,
                source_path=path,
                sensitivity=source.sensitivity,
                document_type="unsupported",
                status=IngestionStatus.FAILED,
                error_message=f"Unsupported format: {ext}",
            )
            self.manifest_store.upsert(manifest)
            raise

        return self._run_ingestion(
            document_id=source.document_id,
            source_hash=source_hash,
            source_path=path,
            filename=source.filename,
            text=text,
            sensitivity=source.sensitivity,
            document_type=doc_type,
            metadata=source.metadata,
            force_reindex=force_reindex,
        )

    def delete_document(self, document_id: str) -> bool:
        """Delete all index entries for a document and update manifest."""
        return self._remove_document(document_id)

    def reindex_document(self, source: KnowledgeSource) -> IndexManifest:
        """Force remove and re-ingest a document."""
        return self.ingest_file(source, force_reindex=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_ingestion(
        self,
        document_id: str,
        source_hash: str,
        source_path: str,
        filename: str,
        text: str,
        sensitivity: str,
        document_type: str,
        metadata: Dict[str, Any],
        force_reindex: bool = False,
    ) -> IndexManifest:
        """Core ingestion: chunk → embed → upsert vector + lexical → manifest."""

        # Prompt injection scan (document content is DATA, never instructions)
        flags = PromptInjectionDefense.scan_for_injection_patterns(text)
        if flags:
            logger.warning(
                "Prompt injection pattern detected in document %s (not blocking ingestion, flagged in metadata).",
                document_id,
            )
            metadata["injection_flags"] = flags

        # Chunking
        try:
            chunks = self.chunker.chunk_text(
                text=text,
                document_id=document_id,
                source_hash=source_hash,
                filename=filename,
                source_path=source_path,
                sensitivity=sensitivity,
                document_type=document_type,
                metadata=metadata,
            )
        except ResourceLimitExceededError:
            raise
        except Exception as e:
            raise IngestionError(
                f"Chunking failed for {filename}: {e}",
                details={"document_id": document_id},
            ) from e

        if not chunks:
            manifest = IndexManifest(
                document_id=document_id,
                source_hash=source_hash,
                filename=filename,
                source_path=source_path,
                chunk_count=0,
                sensitivity=sensitivity,
                document_type=document_type,
                status=IngestionStatus.INDEXED,
            )
            self.manifest_store.upsert(manifest)
            return manifest

        # Set embedding model on chunks
        for chunk in chunks:
            chunk.embedding_model = self.embedder.model_name

        # Embedding
        texts = [c.text for c in chunks]
        try:
            embeddings = self.embedder.embed_texts(texts)
        except Exception as e:
            raise IngestionError(
                f"Embedding failed for {filename}: {e}",
                details={"document_id": document_id},
            ) from e

        # Ensure Qdrant collection exists
        try:
            self.vector_store.create_collection()
        except Exception as e:
            raise IngestionError(
                f"Failed to create/verify vector store collection: {e}",
                details={"document_id": document_id},
            ) from e

        # Upsert to vector store
        try:
            self.vector_store.upsert(chunks, embeddings)
        except Exception as e:
            raise IngestionError(
                f"Vector upsert failed for {filename}: {e}",
                details={"document_id": document_id},
            ) from e

        # Add to BM25 lexical index
        try:
            self.lexical_index.add_chunks(chunks)
        except Exception as e:
            logger.warning("BM25 indexing failed (non-fatal): %s", e)

        # Create manifest
        manifest = IndexManifest(
            document_id=document_id,
            source_hash=source_hash,
            filename=filename,
            source_path=source_path,
            chunk_count=len(chunks),
            embedding_model=self.embedder.model_name,
            embedding_dimension=self.embedder.dimension,
            chunking_version=CHUNKING_VERSION,
            index_version=INDEX_VERSION,
            sensitivity=sensitivity,
            document_type=document_type,
            status=IngestionStatus.INDEXED,
        )
        self.manifest_store.upsert(manifest)
        logger.info(
            "Ingested document_id=%s, %d chunks, sensitivity=%s",
            document_id, len(chunks), sensitivity,
        )
        return manifest

    def _extract_text(self, path: str, ext: str) -> Tuple[str, str]:
        """Extract text from a file. Returns (text, document_type)."""
        if ext in SUPPORTED_TEXT_EXTENSIONS:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(), "text"

        if ext == SUPPORTED_PDF_EXTENSION:
            return self._extract_pdf(path)

        raise UnsupportedFormatError(
            f"Unsupported file extension '{ext}'. Supported: "
            f"{SUPPORTED_TEXT_EXTENSIONS | {SUPPORTED_PDF_EXTENSION}}",
        )

    def _extract_pdf(self, path: str) -> Tuple[str, str]:
        """Extract text from PDF using Phase 6 PDFProcessor."""
        try:
            from backend.app.multimodal.pdf_processor import PDFProcessor
            processor = PDFProcessor()
            pages = processor.extract_text(path)
            full_text = "\n\n".join(
                f"[Page {p.get('page_number', i+1)}]\n{p.get('text', '')}"
                for i, p in enumerate(pages)
                if p.get("text", "").strip()
            )
            return full_text, "pdf"
        except Exception as e:
            # Graceful degradation: return empty string rather than crash
            logger.warning("PDF extraction failed for %s: %s", path, e)
            return "", "pdf"

    def _remove_document(self, document_id: str) -> bool:
        """Remove all index entries for document_id."""
        manifest = self.manifest_store.get(document_id)
        if manifest:
            source_hash = manifest.source_hash
            # Remove from vector store by source_hash
            self.vector_store.delete_by_source_hash(source_hash)
            # Remove from BM25 index
            self.lexical_index.delete_by_source_hash(source_hash)
            # Mark manifest as deleted
            manifest.status = IngestionStatus.DELETED
            manifest.updated_at = datetime.now(timezone.utc).isoformat()
            self.manifest_store.upsert(manifest)
            logger.info("Removed document_id=%s (source_hash=%s)", document_id, source_hash[:16])
            return True
        return False

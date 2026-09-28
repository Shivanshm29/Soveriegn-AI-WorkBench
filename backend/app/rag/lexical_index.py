"""Local BM25 lexical index for Phase 8 RAG - exact identifier and keyword search."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.rag.errors import LexicalIndexUnavailableError
from backend.app.rag.schemas import KnowledgeChunk, RetrievalResult

logger = logging.getLogger("app.rag.lexical_index")

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    BM25Okapi = None


def _tokenize(text: str) -> List[str]:
    """Tokenize preserving identifiers, numbers, and technical terms."""
    # Preserve alphanumeric runs including hyphens/underscores (part numbers, IDs)
    tokens = re.findall(r"[A-Za-z0-9](?:[A-Za-z0-9\-_\.]*[A-Za-z0-9])?", text.lower())
    return [t for t in tokens if len(t) > 0]


class LexicalIndex:
    """
    Local BM25 index for lexical / exact-identifier retrieval.

    Fully in-memory; optionally persisted to a local JSON file.
    No external services involved.
    """

    def __init__(self, persist_path: Optional[str] = None):
        if not BM25_AVAILABLE:
            raise LexicalIndexUnavailableError(
                "rank-bm25 is not installed. Install with: pip install rank-bm25"
            )
        self.persist_path = persist_path
        self._chunks: List[Dict[str, Any]] = []   # parallel list to BM25 corpus
        self._corpus: List[List[str]] = []         # tokenized documents
        self._bm25: Optional[Any] = None

    def _rebuild(self) -> None:
        """Rebuild the BM25 index from the current corpus."""
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None

    def add_chunks(self, chunks: List[KnowledgeChunk]) -> None:
        """Add chunks to the lexical index and rebuild."""
        for chunk in chunks:
            tokens = _tokenize(chunk.text)
            self._corpus.append(tokens)
            self._chunks.append({
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "source_hash": chunk.source_hash,
                "filename": chunk.filename,
                "text": chunk.text,
                "page_number": chunk.page_number,
                "section": chunk.section,
                "sensitivity": chunk.sensitivity,
                "metadata": chunk.metadata,
                "is_table": chunk.is_table,
                "table_headers": chunk.table_headers,
                "table_rows": chunk.table_rows,
            })
        self._rebuild()
        logger.debug("BM25 index rebuilt with %d documents.", len(self._chunks))

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_hash_filter: Optional[str] = None,
        sensitivity_filter: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """BM25 search returning ranked RetrievalResults."""
        if self._bm25 is None or not self._chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Sort by score descending
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )

        results: List[RetrievalResult] = []
        rank = 1
        for idx, score in ranked:
            if score <= 0:
                continue
            if rank > top_k:
                break

            meta = self._chunks[idx]

            # Apply optional filters
            if source_hash_filter and meta.get("source_hash") != source_hash_filter:
                continue
            if sensitivity_filter:
                # Only include docs at or below requested sensitivity
                pass  # Handled at access-control layer

            results.append(
                RetrievalResult(
                    document_id=meta["document_id"],
                    chunk_id=meta["chunk_id"],
                    source_hash=meta["source_hash"],
                    filename=meta.get("filename", ""),
                    text=meta["text"],
                    page_number=meta.get("page_number"),
                    section=meta.get("section"),
                    lexical_score=float(score),
                    lexical_rank=rank,
                    sensitivity=meta.get("sensitivity", "INTERNAL"),
                    metadata=meta.get("metadata", {}),
                    is_table=meta.get("is_table", False),
                    table_headers=meta.get("table_headers"),
                    table_rows=meta.get("table_rows"),
                )
            )
            rank += 1

        return results

    def delete_by_source_hash(self, source_hash: str) -> int:
        """Remove all entries for a given source hash and rebuild the index."""
        original_count = len(self._chunks)
        filtered_pairs = [
            (chunk, tokens)
            for chunk, tokens in zip(self._chunks, self._corpus)
            if chunk.get("source_hash") != source_hash
        ]
        if not filtered_pairs:
            self._chunks = []
            self._corpus = []
        else:
            self._chunks, self._corpus = zip(*filtered_pairs)
            self._chunks = list(self._chunks)
            self._corpus = list(self._corpus)
        self._rebuild()
        removed = original_count - len(self._chunks)
        logger.info("Removed %d BM25 entries for source_hash=%s", removed, source_hash[:16])
        return removed

    def count(self) -> int:
        """Return the number of indexed documents."""
        return len(self._chunks)

    def save(self, path: Optional[str] = None) -> None:
        """Persist the lexical index to a local JSON file."""
        target = path or self.persist_path
        if not target:
            return
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump({
                "chunks": self._chunks,
                "corpus": self._corpus,
            }, f)
        logger.info("BM25 index persisted to %s (%d docs)", target, len(self._chunks))

    def load(self, path: Optional[str] = None) -> bool:
        """Load a persisted lexical index from a local JSON file. Returns True on success."""
        target = path or self.persist_path
        if not target or not os.path.exists(target):
            return False
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._chunks = data.get("chunks", [])
            self._corpus = data.get("corpus", [])
            self._rebuild()
            logger.info("BM25 index loaded from %s (%d docs)", target, len(self._chunks))
            return True
        except Exception as e:
            logger.warning("Failed to load BM25 index from %s: %s", target, e)
            return False

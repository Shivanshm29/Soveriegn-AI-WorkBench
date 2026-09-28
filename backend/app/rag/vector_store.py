"""Local Qdrant vector store abstraction for Phase 8 RAG."""

import logging
from typing import Any, Dict, List, Optional

from backend.app.rag.errors import (
    VectorStoreUnavailableError,
    EmbeddingDimensionMismatchError,
)
from backend.app.rag.schemas import KnowledgeChunk, RetrievalResult

logger = logging.getLogger("app.rag.vector_store")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None


class VectorStore:
    """
    Clean abstraction over a local Qdrant instance.

    Sovereignty guarantee: Only localhost/local paths accepted.
    No cloud Qdrant endpoints permitted.
    """

    SOVEREIGN_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "knowledge_base",
        embedding_dim: int = 384,
        use_in_memory: bool = True,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.use_in_memory = use_in_memory
        self._client: Optional[Any] = None

        if not QDRANT_AVAILABLE:
            raise VectorStoreUnavailableError(
                "qdrant-client is not installed. Install with: pip install qdrant-client"
            )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                if self.use_in_memory:
                    self._client = QdrantClient(":memory:")
                else:
                    # Sovereign host validation
                    if self.host not in self.SOVEREIGN_ALLOWED_HOSTS:
                        raise VectorStoreUnavailableError(
                            f"Non-local Qdrant host '{self.host}' rejected by sovereignty policy. "
                            f"Only local hosts are permitted: {self.SOVEREIGN_ALLOWED_HOSTS}",
                        )
                    self._client = QdrantClient(host=self.host, port=self.port)
            except VectorStoreUnavailableError:
                raise
            except Exception as e:
                raise VectorStoreUnavailableError(
                    f"Failed to connect to local Qdrant at {self.host}:{self.port}: {e}"
                ) from e
        return self._client

    def health(self) -> bool:
        """Return True if the vector store is reachable and healthy."""
        try:
            client = self._get_client()
            client.get_collections()
            return True
        except Exception:
            return False

    def collection_exists(self, name: Optional[str] = None) -> bool:
        """Check if the collection exists."""
        col = name or self.collection_name
        try:
            client = self._get_client()
            collections = client.get_collections().collections
            return any(c.name == col for c in collections)
        except Exception:
            return False

    def create_collection(
        self,
        name: Optional[str] = None,
        dim: Optional[int] = None,
        recreate: bool = False,
    ) -> None:
        """Create a collection. Raises if dimension mismatch detected."""
        col = name or self.collection_name
        d = dim or self.embedding_dim
        client = self._get_client()

        if self.collection_exists(col):
            if recreate:
                client.delete_collection(col)
            else:
                # Verify dimensions match
                info = client.get_collection(col)
                existing_dim = info.config.params.vectors.size
                if existing_dim != d:
                    raise EmbeddingDimensionMismatchError(
                        f"Existing collection '{col}' has dim={existing_dim}, "
                        f"but embedder produces dim={d}.",
                        details={"collection": col, "existing_dim": existing_dim, "new_dim": d},
                    )
                return

        client.create_collection(
            collection_name=col,
            vectors_config=VectorParams(size=d, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' with dim=%d", col, d)

    def upsert(self, chunks: List[KnowledgeChunk], embeddings: List[List[float]]) -> int:
        """Upsert chunks with their embeddings. Returns number of points upserted."""
        if not chunks or not embeddings:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings lists must have the same length.")

        client = self._get_client()
        if not self.collection_exists():
            self.create_collection()

        points = []
        for chunk, vec in zip(chunks, embeddings):
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "source_hash": chunk.source_hash,
                "filename": chunk.filename,
                "source_path": chunk.source_path,
                "text": chunk.text,
                "page_number": chunk.page_number,
                "section": chunk.section,
                "chunk_index": chunk.chunk_index,
                "sensitivity": chunk.sensitivity,
                "document_type": chunk.document_type,
                "extraction_method": chunk.extraction_method,
                "is_table": chunk.is_table,
                "table_headers": chunk.table_headers,
                "table_rows": chunk.table_rows,
                "metadata": chunk.metadata,
            }
            # Use deterministic vector ID based on content identity
            vid = abs(hash(chunk.vector_id)) % (2**63)
            points.append(PointStruct(id=vid, vector=vec, payload=payload))

        client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Semantic search returning ranked RetrievalResults."""
        client = self._get_client()
        if not self.collection_exists():
            return []

        qdrant_filter = None
        if filters:
            conditions = []
            for key, val in filters.items():
                if val is not None:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))
            if conditions:
                qdrant_filter = Filter(must=conditions)

        try:
            hits = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except Exception as e:
            raise VectorStoreUnavailableError(
                f"Qdrant search failed: {e}",
                details={"collection": self.collection_name},
            ) from e

        results = []
        for rank, hit in enumerate(hits, start=1):
            p = hit.payload or {}
            results.append(
                RetrievalResult(
                    document_id=p.get("document_id", ""),
                    chunk_id=p.get("chunk_id", ""),
                    source_hash=p.get("source_hash", ""),
                    filename=p.get("filename", ""),
                    text=p.get("text", ""),
                    page_number=p.get("page_number"),
                    section=p.get("section"),
                    dense_score=float(hit.score),
                    dense_rank=rank,
                    sensitivity=p.get("sensitivity", "INTERNAL"),
                    metadata=p.get("metadata", {}),
                    is_table=p.get("is_table", False),
                    table_headers=p.get("table_headers"),
                    table_rows=p.get("table_rows"),
                )
            )
        return results

    def delete_by_source_hash(self, source_hash: str) -> int:
        """Delete all points belonging to a specific source document hash."""
        client = self._get_client()
        if not self.collection_exists():
            return 0
        try:
            client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="source_hash", match=MatchValue(value=source_hash))]
                ),
            )
            logger.info("Deleted points for source_hash=%s", source_hash[:16])
            return 1
        except Exception as e:
            logger.warning("Failed to delete by source_hash: %s", e)
            return 0

    def count(self) -> int:
        """Return the total number of points in the collection."""
        try:
            client = self._get_client()
            info = client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def get(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single point payload by chunk_id (linear scan via scroll)."""
        client = self._get_client()
        if not self.collection_exists():
            return None
        try:
            results, _ = client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
                ),
                limit=1,
                with_payload=True,
            )
            if results:
                return results[0].payload
            return None
        except Exception:
            return None

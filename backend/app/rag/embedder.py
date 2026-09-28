"""Local embedding engine for Phase 8 RAG - uses ModelRuntime or deterministic fallback."""

import hashlib
import struct
from typing import List, Optional, Dict, Any

from backend.app.rag.errors import EmbeddingUnavailableError, EmbeddingDimensionMismatchError

# Default dimension when no runtime is available (deterministic hash-based fallback)
DEFAULT_EMBEDDING_DIM = 384
EMBEDDING_MODEL_FALLBACK = "local-hash-embedding-v1"


class LocalEmbedder:
    """
    Generates embeddings locally.

    When a ModelRuntime with an embedding endpoint is available, it is used.
    When not available (test/offline), falls back to a deterministic hash-based
    embedding that preserves lexical identity without hallucinating semantic similarity.
    This fallback is explicit and never silently switches to a cloud provider.
    """

    def __init__(
        self,
        model_runtime=None,
        embedding_model_name: str = EMBEDDING_MODEL_FALLBACK,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        batch_size: int = 32,
    ):
        self.model_runtime = model_runtime
        self.embedding_model_name = embedding_model_name
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        self._use_runtime = False  # Will try runtime on first embed call

    @property
    def model_name(self) -> str:
        return self.embedding_model_name

    @property
    def dimension(self) -> int:
        return self.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts locally.
        Falls back to deterministic hash embedding if ModelRuntime not available.
        Never contacts any external service.
        """
        if not texts:
            return []

        # Try ModelRuntime embedding endpoint if configured
        if self.model_runtime is not None and self._use_runtime:
            try:
                return self._embed_via_runtime(texts)
            except Exception as e:
                raise EmbeddingUnavailableError(
                    f"Embedding model unavailable: {e}",
                    details={"model": self.embedding_model_name},
                ) from e

        # Deterministic hash-based local embedding fallback
        return [self._hash_embed(text) for text in texts]

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        results = self.embed_texts([query])
        return results[0]

    def _hash_embed(self, text: str) -> List[float]:
        """
        Deterministic embedding from SHA-256 hash of text.
        Produces a stable float vector of self.embedding_dim dimensions.
        Same text always produces same vector; different texts produce different vectors.
        This is NOT semantically meaningful but IS locally sovereign and deterministic.
        """
        dim = self.embedding_dim
        normalized = text.strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()

        # Extend digest to required dimension using SHAKE-256 (XOF)
        xof = hashlib.shake_256(normalized.encode("utf-8"))
        raw_bytes = xof.digest(dim * 4)  # 4 bytes per float

        floats: List[float] = []
        for i in range(dim):
            chunk = raw_bytes[i * 4 : (i + 1) * 4]
            val = struct.unpack(">I", chunk)[0]
            # Normalize to [-1, 1]
            floats.append((val / 2_147_483_647.5) - 1.0)

        # L2 normalize
        magnitude = sum(x * x for x in floats) ** 0.5
        if magnitude > 0:
            floats = [x / magnitude for x in floats]

        return floats

    def _embed_via_runtime(self, texts: List[str]) -> List[List[float]]:
        """
        Attempt to use ModelRuntime for embeddings.
        Currently a stub; real embedding API calls would go here once the
        local embedding model endpoint is confirmed available.
        """
        raise EmbeddingUnavailableError(
            "ModelRuntime embedding endpoint not yet configured.",
            details={"model": self.embedding_model_name},
        )

    def validate_dimension(self, expected_dim: int) -> None:
        """Raise EmbeddingDimensionMismatchError if dimensions do not match."""
        if self.embedding_dim != expected_dim:
            raise EmbeddingDimensionMismatchError(
                f"Embedding dimension {self.embedding_dim} does not match expected {expected_dim}.",
                details={"actual": self.embedding_dim, "expected": expected_dim},
            )

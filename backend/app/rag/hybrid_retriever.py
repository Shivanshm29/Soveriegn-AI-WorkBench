"""Hybrid retriever combining dense (Qdrant) and lexical (BM25) with RRF fusion."""

import logging
from typing import Any, Dict, List, Optional

from backend.app.rag.schemas import EvidencePack, QueryAnalysis, RetrievalResult
from backend.app.rag.vector_store import VectorStore
from backend.app.rag.lexical_index import LexicalIndex
from backend.app.rag.embedder import LocalEmbedder
from backend.app.rag.errors import RetrievalError, UnauthorizedRetrievalError
from backend.app.security.data_sensitivity import DataSensitivity

logger = logging.getLogger("app.rag.retriever")

# Sensitivity ordering: PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED
_SENSITIVITY_ORDER = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}

# Default RRF k constant
RRF_K = 60


def _sensitivity_allowed(chunk_sensitivity: str, max_allowed: str) -> bool:
    """Return True if chunk_sensitivity <= max_allowed sensitivity."""
    chunk_level = _SENSITIVITY_ORDER.get(chunk_sensitivity.upper(), 99)
    max_level = _SENSITIVITY_ORDER.get(max_allowed.upper(), 1)
    return chunk_level <= max_level


def reciprocal_rank_fusion(
    dense_results: List[RetrievalResult],
    lexical_results: List[RetrievalResult],
    k: int = RRF_K,
) -> List[RetrievalResult]:
    """
    Deterministic Reciprocal Rank Fusion.

    RRF_score(d) = sum(1 / (k + rank_i(d))) across all retrieval methods.
    Merges dense and lexical rankings into a single fused result list.
    """
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, RetrievalResult] = {}

    # Accumulate dense scores
    for rank, result in enumerate(dense_results, start=1):
        key = result.chunk_id
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunk_map:
            chunk_map[key] = result.model_copy(deep=True)
        chunk_map[key].dense_rank = rank
        chunk_map[key].dense_score = result.dense_score

    # Accumulate lexical scores
    for rank, result in enumerate(lexical_results, start=1):
        key = result.chunk_id
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunk_map:
            chunk_map[key] = result.model_copy(deep=True)
        chunk_map[key].lexical_rank = rank
        chunk_map[key].lexical_score = result.lexical_score

    # Apply fusion scores and sort descending
    for key, score in scores.items():
        chunk_map[key].fusion_score = round(score, 8)

    fused = sorted(chunk_map.values(), key=lambda r: r.fusion_score, reverse=True)
    return fused


class HybridRetriever:
    """
    Combines dense vector search and BM25 lexical retrieval via RRF.

    Sovereignty guarantee: All retrieval is local. No external calls.
    Access control: Sensitivity-based filtering applied before results are returned.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        lexical_index: LexicalIndex,
        embedder: LocalEmbedder,
        rrf_k: int = RRF_K,
        default_top_k: int = 10,
        max_top_k: int = 50,
    ):
        self.vector_store = vector_store
        self.lexical_index = lexical_index
        self.embedder = embedder
        self.rrf_k = rrf_k
        self.default_top_k = default_top_k
        self.max_top_k = max_top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        max_sensitivity: str = "INTERNAL",
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval:
        1. Dense search via Qdrant
        2. BM25 lexical search
        3. RRF fusion
        4. Sensitivity filtering (access control)
        """
        k = min(top_k or self.default_top_k, self.max_top_k)

        # Dense retrieval
        try:
            query_vec = self.embedder.embed_query(query)
            dense_results = self.vector_store.search(
                query_vector=query_vec,
                top_k=k * 2,  # Over-fetch before filtering
                filters=metadata_filters,
            )
        except Exception as e:
            logger.warning("Dense retrieval failed: %s — falling back to lexical only.", e)
            dense_results = []

        # Lexical retrieval
        try:
            lexical_results = self.lexical_index.search(query=query, top_k=k * 2)
        except Exception as e:
            logger.warning("Lexical retrieval failed: %s — falling back to dense only.", e)
            lexical_results = []

        if not dense_results and not lexical_results:
            return []

        # RRF fusion
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            lexical_results=lexical_results,
            k=self.rrf_k,
        )

        # Sensitivity-based access control (fail-closed)
        authorized = [
            r for r in fused
            if _sensitivity_allowed(r.sensitivity, max_sensitivity)
        ]

        if len(authorized) < len(fused):
            filtered_count = len(fused) - len(authorized)
            logger.info(
                "Sensitivity filter blocked %d/%d results (max_allowed=%s).",
                filtered_count, len(fused), max_sensitivity,
            )

        return authorized[:k]

    def build_evidence_pack(
        self,
        query: str,
        results: List[RetrievalResult],
        query_analysis: Optional[QueryAnalysis] = None,
        max_evidence_tokens: int = 3000,
    ) -> EvidencePack:
        """
        Create a structured EvidencePack from retrieved results.
        Estimates token count and truncates if necessary.
        """
        # Rough token estimate: 1 token ~ 4 chars
        total_chars = sum(len(r.text) for r in results)
        token_estimate = total_chars // 4

        # Truncate if exceeding budget
        selected = results
        if token_estimate > max_evidence_tokens:
            budget = max_evidence_tokens * 4
            cumulative = 0
            selected = []
            for r in results:
                if cumulative + len(r.text) <= budget:
                    selected.append(r)
                    cumulative += len(r.text)
                else:
                    break

        return EvidencePack(
            query=query,
            results=selected,
            total_retrieved=len(results),
            evidence_token_estimate=sum(len(r.text) for r in selected) // 4,
            query_analysis=query_analysis.model_dump() if query_analysis else None,
        )

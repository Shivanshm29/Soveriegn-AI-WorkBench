"""Phase 8 Knowledge Agent - sovereign hybrid RAG agent integrated with AgentRegistry."""

import logging
from typing import Any, Dict, List, Optional

from backend.app.rag.schemas import (
    EvidencePack,
    GroundedAnswer,
    IndexManifest,
    KnowledgeSource,
    QueryAnalysis,
    RAGVerificationReport,
    RetrievalResult,
)
from backend.app.rag.errors import (
    RAGError,
    RetrievalError,
    UnauthorizedRetrievalError,
    IngestionError,
)
from backend.app.rag.embedder import LocalEmbedder
from backend.app.rag.vector_store import VectorStore
from backend.app.rag.lexical_index import LexicalIndex
from backend.app.rag.hybrid_retriever import HybridRetriever
from backend.app.rag.query_processor import QueryProcessor
from backend.app.rag.grounded_generation import GroundedGenerator, RAGVerifier
from backend.app.rag.ingestion import KnowledgeIngestionPipeline
from backend.app.rag.manifest import ManifestStore
from backend.app.rag.chunker import DocumentChunker

logger = logging.getLogger("app.rag.knowledge_agent")

KNOWLEDGE_AGENT_ID = "knowledge_agent"


def build_default_knowledge_agent(
    model_runtime=None,
    manifest_path: str = "data/knowledge/manifest.json",
    bm25_path: str = "data/knowledge/bm25_index.json",
    embedding_dim: int = 384,
) -> "KnowledgeAgent":
    """
    Factory that wires all Phase 8 components together.
    Uses in-memory Qdrant (always local, no external service required).
    """
    embedder = LocalEmbedder(
        model_runtime=model_runtime,
        embedding_dim=embedding_dim,
    )
    vector_store = VectorStore(
        collection_name="sovereign_knowledge",
        embedding_dim=embedding_dim,
        use_in_memory=True,  # No external Qdrant required
    )
    lexical_index = LexicalIndex(persist_path=bm25_path)
    # Attempt to load existing BM25 index from disk
    lexical_index.load()

    manifest_store = ManifestStore(path=manifest_path)
    chunker = DocumentChunker()

    ingestion_pipeline = KnowledgeIngestionPipeline(
        vector_store=vector_store,
        lexical_index=lexical_index,
        embedder=embedder,
        manifest_store=manifest_store,
        chunker=chunker,
    )

    retriever = HybridRetriever(
        vector_store=vector_store,
        lexical_index=lexical_index,
        embedder=embedder,
    )

    generator = GroundedGenerator(
        model_runtime=model_runtime,
        model_name="Qwen/Qwen3-4B",
    )

    return KnowledgeAgent(
        ingestion_pipeline=ingestion_pipeline,
        retriever=retriever,
        generator=generator,
        query_processor=QueryProcessor(),
        verifier=RAGVerifier(),
        manifest_store=manifest_store,
    )


class KnowledgeAgent:
    """
    Sovereign Knowledge Agent providing:
    - knowledge.ingest: Add documents to the local knowledge base
    - knowledge.search: Hybrid retrieval (dense + BM25 + RRF)
    - knowledge.grounded_answer: Local LLM grounded generation with citations
    - knowledge.verify: Citation verification
    - knowledge.delete_source: Remove documents and invalidate stale chunks

    All operations are local. No external services permitted.
    Phase 5 policy controls remain authoritative for sensitivity decisions.
    """

    def __init__(
        self,
        ingestion_pipeline: KnowledgeIngestionPipeline,
        retriever: HybridRetriever,
        generator: GroundedGenerator,
        query_processor: QueryProcessor,
        verifier: RAGVerifier,
        manifest_store: ManifestStore,
    ):
        self.ingestion = ingestion_pipeline
        self.retriever = retriever
        self.generator = generator
        self.query_processor = query_processor
        self.verifier = verifier
        self.manifest_store = manifest_store

    # ------------------------------------------------------------------
    # knowledge.ingest
    # ------------------------------------------------------------------

    def ingest_text(
        self,
        text: str,
        document_id: str,
        filename: str = "inline_text",
        sensitivity: str = "INTERNAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IndexManifest:
        """Index raw text into the knowledge base."""
        return self.ingestion.ingest_text(
            text=text,
            document_id=document_id,
            filename=filename,
            sensitivity=sensitivity,
            metadata=metadata or {},
        )

    def ingest_file(self, source: KnowledgeSource) -> IndexManifest:
        """Index a document file into the knowledge base."""
        return self.ingestion.ingest_file(source)

    # ------------------------------------------------------------------
    # knowledge.search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        max_sensitivity: str = "INTERNAL",
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval (dense + BM25 + RRF).
        Sensitivity-based access control is applied before results are returned.
        Unauthorized evidence never enters the result set.
        """
        analysis = self.query_processor.analyze(
            query=query,
            sensitivity_scope=max_sensitivity,
            metadata_filters=metadata_filters,
        )
        augmented_query = self.query_processor.build_augmented_query(analysis)

        results = self.retriever.retrieve(
            query=augmented_query,
            top_k=top_k,
            max_sensitivity=max_sensitivity,
            metadata_filters=metadata_filters,
        )
        logger.info(
            "search(query=%r) → %d results (max_sensitivity=%s)",
            query[:60], len(results), max_sensitivity,
        )
        return results

    # ------------------------------------------------------------------
    # knowledge.grounded_answer
    # ------------------------------------------------------------------

    def grounded_answer(
        self,
        query: str,
        top_k: int = 8,
        max_sensitivity: str = "INTERNAL",
        max_evidence_tokens: int = 3000,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> GroundedAnswer:
        """
        Full RAG pipeline:
        1. Hybrid retrieval
        2. Evidence pack construction
        3. Local LLM grounded generation
        4. Citation verification
        """
        results = self.search(
            query=query,
            top_k=top_k,
            max_sensitivity=max_sensitivity,
            metadata_filters=metadata_filters,
        )

        pack = self.retriever.build_evidence_pack(
            query=query,
            results=results,
            max_evidence_tokens=max_evidence_tokens,
        )

        answer = self.generator.generate(pack=pack, user_query=query)

        # Verify citations
        report = self.verifier.verify(answer=answer, pack=pack)
        logger.info(
            "grounded_answer: verification=%s, citations=%d",
            report.status, len(answer.citations),
        )

        return answer

    answer_query = grounded_answer


    # ------------------------------------------------------------------
    # knowledge.verify
    # ------------------------------------------------------------------

    def verify_answer(
        self,
        answer: GroundedAnswer,
        pack: EvidencePack,
    ) -> RAGVerificationReport:
        """Standalone citation and evidence verification."""
        return self.verifier.verify(answer=answer, pack=pack)

    # ------------------------------------------------------------------
    # knowledge.delete_source
    # ------------------------------------------------------------------

    def delete_source(self, document_id: str) -> bool:
        """
        Remove all index entries for a document and invalidate stale chunks.
        This is an auditable operation — the manifest is updated to DELETED.
        """
        result = self.ingestion.delete_document(document_id)
        logger.info("delete_source(document_id=%s) → %s", document_id, result)
        return result

    # ------------------------------------------------------------------
    # Metadata / state
    # ------------------------------------------------------------------

    def list_indexed_documents(self) -> List[IndexManifest]:
        """Return all manifests currently in the knowledge base."""
        return self.manifest_store.list()

    def get_manifest(self, document_id: str) -> Optional[IndexManifest]:
        """Retrieve the manifest for a specific document."""
        return self.manifest_store.get(document_id)

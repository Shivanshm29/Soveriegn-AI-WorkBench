"""Phase 8 RAG tools for ToolRegistry."""

from typing import List
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry


def get_rag_tools() -> List[ToolContract]:
    """Define Phase 8 knowledge retrieval tools."""
    return [
        ToolContract(
            tool_id="knowledge_ingest",
            name="Knowledge Ingest",
            description="Ingests a local document into the sovereign knowledge base (vector + BM25 indexes).",
            capabilities=["knowledge.ingest", "knowledge_ingestion"],
            risk_level="MEDIUM",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "document_id": {"type": "string"},
                    "sensitivity": {"type": "string"},
                },
                "required": ["source_path"],
            },
            output_schema={
                "type": "object",
                "properties": {"manifest": {"type": "object"}, "status": {"type": "string"}},
            },
        ),
        ToolContract(
            tool_id="knowledge_search",
            name="Knowledge Search",
            description="Performs hybrid (dense + BM25 + RRF) search against the local knowledge base.",
            capabilities=["knowledge.search", "knowledge.hybrid_retrieval", "knowledge_search"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                    "max_sensitivity": {"type": "string"},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
        ),
        ToolContract(
            tool_id="knowledge_retrieve",
            name="Knowledge Retrieve (Grounded Answer)",
            description="Full RAG pipeline: hybrid retrieval + evidence pack + local LLM grounded answer + citations.",
            capabilities=["knowledge.grounded_answer", "knowledge.document_lookup"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                    "max_sensitivity": {"type": "string"},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "citations": {"type": "array"},
                    "verification_passed": {"type": "boolean"},
                },
            },
        ),
        ToolContract(
            tool_id="knowledge_verify",
            name="Knowledge Verify",
            description="Deterministically verifies that all citations in a grounded answer map to existing evidence.",
            capabilities=["knowledge.verify", "citation_verification"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "object"},
                    "evidence_pack": {"type": "object"},
                },
                "required": ["answer", "evidence_pack"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "status": {"type": "string"},
                    "failed_checks": {"type": "array"},
                },
            },
        ),
        ToolContract(
            tool_id="knowledge_delete_source",
            name="Knowledge Delete Source",
            description="Removes all index entries for a document and invalidates stale chunks. Auditable operation.",
            capabilities=["knowledge.delete_source"],
            risk_level="MEDIUM",
            requires_approval=True,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                },
                "required": ["document_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                },
            },
        ),
    ]


def register_rag_tools(registry: ToolRegistry) -> None:
    """Register all Phase 8 RAG tools into the provided ToolRegistry."""
    for tool in get_rag_tools():
        registry.register(tool, overwrite=True)

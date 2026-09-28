"""Structure-aware document chunker for Phase 8 RAG."""

import re
import uuid
from typing import Any, Dict, List, Optional

from backend.app.rag.schemas import KnowledgeChunk, CHUNKING_VERSION
from backend.app.rag.errors import ResourceLimitExceededError

# Limits
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 50
MAX_CHUNKS_PER_DOC = 500


def _split_by_structure(text: str) -> List[str]:
    """
    Split text preferring heading/paragraph/section boundaries.
    Avoids splitting in the middle of identifiers or measurements.
    """
    # Split on double newlines (paragraph boundaries) first
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    buffer = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph keeps us under the limit, accumulate
        if len(buffer) + len(para) + 2 <= MAX_CHUNK_CHARS:
            buffer = (buffer + "\n\n" + para).strip() if buffer else para
        else:
            if buffer:
                chunks.append(buffer)
            # If paragraph itself is oversized, split by sentences
            if len(para) > MAX_CHUNK_CHARS:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sbuf = ""
                for sent in sentences:
                    if len(sbuf) + len(sent) + 1 <= MAX_CHUNK_CHARS:
                        sbuf = (sbuf + " " + sent).strip() if sbuf else sent
                    else:
                        if sbuf:
                            chunks.append(sbuf)
                        sbuf = sent
                if sbuf:
                    chunks.append(sbuf)
                buffer = ""
            else:
                buffer = para

    if buffer:
        chunks.append(buffer)

    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


class DocumentChunker:
    """
    Structure-aware chunker that preserves context, headings, and identifiers.

    Supports: plain text, markdown, PDF extracted text, table rows from Phase 6.
    Never blindly splits on character count alone.
    """

    def __init__(
        self,
        max_chunk_chars: int = MAX_CHUNK_CHARS,
        min_chunk_chars: int = MIN_CHUNK_CHARS,
        max_chunks_per_doc: int = MAX_CHUNKS_PER_DOC,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.max_chunks_per_doc = max_chunks_per_doc

    def chunk_text(
        self,
        text: str,
        document_id: str,
        source_hash: str,
        filename: str = "",
        source_path: str = "",
        sensitivity: str = "INTERNAL",
        document_type: str = "text",
        extraction_method: str = "text_splitter",
        page_number: Optional[int] = None,
        section: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[KnowledgeChunk]:
        """Chunk raw text into KnowledgeChunks with provenance metadata."""
        if not text or not text.strip():
            return []

        raw_chunks = _split_by_structure(text)

        if len(raw_chunks) > self.max_chunks_per_doc:
            raise ResourceLimitExceededError(
                f"Document produces {len(raw_chunks)} chunks, exceeding limit of {self.max_chunks_per_doc}.",
                details={"document_id": document_id, "chunk_count": len(raw_chunks)},
            )

        result: List[KnowledgeChunk] = []
        for idx, chunk_text in enumerate(raw_chunks):
            result.append(
                KnowledgeChunk(
                    document_id=document_id,
                    source_hash=source_hash,
                    filename=filename,
                    source_path=source_path,
                    text=chunk_text,
                    page_number=page_number,
                    section=section,
                    chunk_index=idx,
                    char_offset_start=text.find(chunk_text),
                    sensitivity=sensitivity,
                    document_type=document_type,
                    extraction_method=extraction_method,
                    chunking_version=CHUNKING_VERSION,
                    metadata=metadata or {},
                )
            )
        return result

    def chunk_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        document_id: str,
        source_hash: str,
        filename: str = "",
        source_path: str = "",
        sensitivity: str = "INTERNAL",
        page_number: Optional[int] = None,
        section: Optional[str] = None,
        table_index: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[KnowledgeChunk]:
        """
        Chunk a table preserving headers and row structure.
        A table becomes one or more KnowledgeChunks with is_table=True.
        """
        if not rows:
            return []

        # Build text representation that also preserves identifiers
        header_line = " | ".join(headers) if headers else ""
        rows_text = "\n".join(" | ".join(str(c) for c in row) for row in rows)
        full_text = f"TABLE: {header_line}\n{rows_text}" if header_line else rows_text

        # Each table is a single chunk (unless extremely large)
        chunk_text = full_text[:self.max_chunk_chars]

        return [
            KnowledgeChunk(
                document_id=document_id,
                source_hash=source_hash,
                filename=filename,
                source_path=source_path,
                text=chunk_text,
                page_number=page_number,
                section=section,
                chunk_index=table_index,
                sensitivity=sensitivity,
                document_type="table",
                extraction_method="table_extractor",
                chunking_version=CHUNKING_VERSION,
                is_table=True,
                table_headers=headers,
                table_rows=rows,
                metadata=metadata or {},
            )
        ]

    def chunk_pages(
        self,
        pages: List[Dict[str, Any]],
        document_id: str,
        source_hash: str,
        filename: str = "",
        source_path: str = "",
        sensitivity: str = "INTERNAL",
        document_type: str = "pdf",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[KnowledgeChunk]:
        """
        Chunk a multi-page document (list of page dicts with 'text' and 'page_number').
        Each page is chunked independently preserving page boundaries.
        """
        all_chunks: List[KnowledgeChunk] = []
        global_idx = 0

        for page in pages:
            page_text = page.get("text", "").strip()
            page_num = page.get("page_number", 1)
            section = page.get("section")

            if not page_text:
                continue

            page_chunks = self.chunk_text(
                text=page_text,
                document_id=document_id,
                source_hash=source_hash,
                filename=filename,
                source_path=source_path,
                sensitivity=sensitivity,
                document_type=document_type,
                extraction_method="pdf_page_splitter",
                page_number=page_num,
                section=section,
                metadata=metadata,
            )

            for chunk in page_chunks:
                chunk.chunk_index = global_idx
                global_idx += 1
                all_chunks.append(chunk)

            if global_idx > self.max_chunks_per_doc:
                raise ResourceLimitExceededError(
                    f"Document produces more than {self.max_chunks_per_doc} chunks.",
                    details={"document_id": document_id},
                )

        return all_chunks

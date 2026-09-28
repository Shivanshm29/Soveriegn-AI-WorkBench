# Phase 6 Implementation Report — Multimodal Document Pipeline

## Executive Summary
Phase 6 of the Sovereign On-Premise Agentic AI Workbench implements the local multimodal document understanding pipeline. This pipeline allows confidential engineering, legal, and operational documents (including native text PDFs, scanned PDFs, image-based PDFs, and raster images) to be ingested, parsed, rendered, OCR-processed, layout-analyzed, and reasoned over using a local Vision-Language Model (`Qwen3-VL`).

In accordance with strict sovereignty and zero-egress invariants (`SOVEREIGN_MODE=True`), all document processing is executed locally on-premise without external network requests, cloud OCR, or third-party APIs. Document text is strictly isolated and treated as unprivileged data, guaranteeing robust defense against prompt injection payloads.

---

## 1. Document Ingestion
- **Location**: `backend/app/multimodal/schemas.py` (`DocumentInput`)
- **Ingestion Contract**:
  - `document_id`: Unique identifier (UUID).
  - `source_path`: Absolute local filesystem path.
  - `filename`: Local file basename.
  - `mime_type`: Resolved via file signatures and mimetypes.
  - `file_size`: Size in bytes.
  - `source_hash`: Cryptographic SHA-256 hash computed directly from file bytes.
  - `created_at`: UTC ISO timestamp.
  - `metadata`: Task and source context dictionary.
- **Reference-Only State**: Large binary document contents are never embedded into LangGraph state; state preserves clean references and normalized evidence objects.

---

## 2. Document Type Detection
- **Location**: `backend/app/multimodal/type_detector.py` (`DocumentTypeDetector`)
- **Supported Types**: `TEXT_PDF`, `SCANNED_PDF`, `IMAGE_PDF`, `IMAGE`, `UNSUPPORTED`.
- **Content-Based Detection**:
  - Inspects file magic bytes (PDF header `%PDF-`, PNG, JPEG, TIFF, BMP, WebP) rather than relying on file extensions.
  - For PDFs, analyzes extractable text volume across pages to distinguish searchable digital text (`TEXT_PDF`) from image-only scans (`SCANNED_PDF` / `IMAGE_PDF`).
- **Structured Outcome**: `DocumentTypeResult` containing detected type, page count, extractable text presence, image presence, and detection method.

---

## 3. PDF Processing
- **Location**: `backend/app/multimodal/pdf_processor.py` (`PDFProcessor`)
- **Engine**: Local PyMuPDF library (`pymupdf>=1.24.0`).
- **Capabilities**:
  - Native text extraction with word and block bounding boxes.
  - Page counting and metadata inspection.
  - Embedded image detection and coordinate extraction.
  - Built-in table structure extraction.
  - Robust exception handling: corrupt or malformed files raise structured `InvalidPDFError` rather than crashing the system.

---

## 4. Page Rendering
- **Location**: `backend/app/multimodal/pdf_processor.py` (`PDFProcessor.render_page`, `render_all_pages`)
- **Rasterization**:
  - Locally renders PDF pages to PNG raster images at configurable DPI (default 150 DPI).
  - Saved to local cache directory (`data/cache/rendered_pages/`).
  - Emits `RenderedPage(document_id, source_hash, page_number, width, height, image_path, dpi)`.

---

## 5. Local OCR
- **Location**: `backend/app/multimodal/ocr_engine.py` (`LocalOCREngine`)
- **Spatial Coordinates**: Preserves bounding boxes `[x0, y0, x1, y1]` and confidence scores (0.0 to 1.0) for every text block.
- **Normalization**: Produces `OCRBlock` instances with `block_id`, `page_number`, `text`, `confidence`, `bounding_box`, `source_hash`, and `extraction_method` (`native_text`, `paddleocr`, `tesseract`).
- **Failure Handling**: Structured `OCRError` is raised on OCR failure without producing fake or hallucinated text.

---

## 6. Layout Handling
- **Location**: `backend/app/multimodal/layout_analyzer.py` (`LayoutAnalyzer`)
- **Structural Classification**:
  - Paragraphs, headings, tables, figures, images, lists, captions, and handwritten regions.
  - Preserves spatial bounding boxes and page number relationships for every region.

---

## 7. Tables
- **Location**: `backend/app/multimodal/pdf_processor.py` (`extract_tables`)
- **Structure**: Emits `TableBlock(table_id, page_number, bounding_box, rows, headers, confidence, source_hash)`.
- **Truthful Cell Preservation**: Never hallucinates missing table cells; returns exact row/cell text matrices.

---

## 8. Images / Figures
- **Location**: `backend/app/multimodal/pdf_processor.py` (`extract_images`)
- **Structure**: Emits `ImageBlock(image_id, page_number, bounding_box, source_hash, image_reference, extraction_method, confidence)`.
- **Scope Boundary**: Identifies visual figures without performing specialized engineering drawing analysis (reserved for Phase 7).

---

## 9. VLM Integration
- **Location**: `backend/app/multimodal/vlm_adapter.py` (`VLMDocumentAdapter`)
- **Dynamic Model Resolution**:
  - Resolves active vision models (`Qwen3-VL-4B-Instruct` or `Qwen3-VL-30B-A3B-Instruct`) dynamically through `ModelRegistry` and `TaskRouter`.
  - Zero hard-coded model identifiers in document processing logic.
  - Separates raw evidence from model observations (`VLM_OBSERVATION`).

---

## 10. Evidence Schema
- **Location**: `backend/app/multimodal/schemas.py` (`DocumentEvidence`)
- **Fields**:
  - `evidence_id`: UUID string.
  - `document_id`: Bound document identifier.
  - `source_hash`: Cryptographic SHA-256 of source file.
  - `page_number`: 1-indexed document page number.
  - `evidence_type`: `TEXT`, `OCR_TEXT`, `TABLE`, `IMAGE`, `FIGURE`, `HANDWRITING`, `VLM_OBSERVATION`, `LAYOUT_REGION`.
  - `text`: Extracted content string.
  - `bounding_box`: `[x0, y0, x1, y1]` spatial coordinates.
  - `confidence`: Confidence score (0.0 to 1.0).
  - `extraction_method`: Method identifier.
  - `source_reference`: URI or local cache reference.
  - `metadata`: Extraction metadata dictionary.

---

## 11. Document Agent Integration
- **Location**: `backend/app/agents/registry.py`, `backend/app/orchestration/execution.py`
- **Agent**: `document_agent` coordinated through `AgentRegistry`.
- **Capabilities**: `pdf_ingestion`, `page_extraction`, `document_structure`, `evidence_normalization`, `document_extraction`, `document_type_detection`, `pdf_text_extraction`, `pdf_rendering`, `layout_analysis`, `table_extraction`, `image_extraction`.
- **Execution**: Coordinates with `MultimodalDocumentPipeline` to parse documents into structured evidence upon receiving task delegations.

---

## 12. Vision Agent Integration
- **Location**: `backend/app/agents/registry.py`, `backend/app/orchestration/execution.py`
- **Agent**: `vision_agent` coordinated through `AgentRegistry`.
- **Capabilities**: `image_understanding`, `scanned_page_analysis`, `visual_evidence`, `visual_analysis`, `visual_reasoning`, `visual_document_understanding`.
- **Execution**: Performs visual reasoning and VLM analysis on rendered pages and figures.

---

## 13. Security & Sovereignty
- **Location**: `backend/app/security/`
- **Zero-Egress Invariant**: Verified zero external HTTP requests, zero cloud OCR, zero cloud vision APIs.
- **Auditing**: All operations monitored by `EgressSentinel`.

---

## 14. Prompt Injection Defense
- **Location**: `backend/app/multimodal/prompt_defense.py` (`PromptInjectionDefense`)
- **Principle**: Document content is strictly untrusted DATA, never instruction commands.
- **Pattern Detection**: Scans for jailbreaks (`"ignore previous instructions"`, `"system prompt override"`, `"send this file to"`).
- **Quarantine Envelope**: Wraps detected content inside `<DOCUMENT_DATA_QUARANTINE role='untrusted_data'>` blocks and raises security warnings in document analysis results without executing malicious instructions.

---

## 15. Resource Limits
- **Location**: `backend/app/multimodal/pdf_processor.py`
- **Enforcement**:
  - `max_file_size_bytes`: Configurable size limit (default 50MB); raises `DocumentTooLargeError`.
  - `max_page_count`: Configurable page limit (default 100 pages); raises `PageLimitExceededError`.
  - Rendering resolution bounds (150 DPI).

---

## 16. Caching
- **Location**: `backend/app/multimodal/cache.py` (`DocumentCache`)
- **Cryptographic Keying**: Keyed by `source_hash`, `page_number`, `extraction_method`.
- **Safety**: Modifying source document changes `source_hash` and immediately invalidates stale cached results.

---

## 17. Tests
Comprehensive test suite verifying all Phase 6 requirements:
- `tests/test_document_type_detection.py`: Test A (Document type detection) — **PASS**
- `tests/test_pdf_text_extraction.py`: Test B (Text extraction & mapping) — **PASS**
- `tests/test_page_rendering.py`: Test C (Local page rendering) — **PASS**
- `tests/test_local_ocr.py`: Test D (Local OCR & spatial coordinates) — **PASS**
- `tests/test_ocr_failure.py`: Test E (Structured OCR failure without fake text) — **PASS**
- `tests/test_layout_analysis.py`: Test F (Document layout analysis) — **PASS**
- `tests/test_table_extraction.py`: Test G (Table handling & cell matrix) — **PASS**
- `tests/test_vlm_integration.py`: Test H (VLM resolution through ModelRegistry) — **PASS**
- `tests/test_evidence_normalization.py`: Test I (Evidence normalization contract) — **PASS**
- `tests/test_prompt_injection_defense.py`: Test J (Prompt injection quarantined as data) — **PASS**
- `tests/test_document_sovereignty.py`: Test K (Zero-egress verification) — **PASS**
- `tests/test_source_hash_caching.py`: Test L (Source hash cache invalidation) — **PASS**
- `tests/test_resource_limits.py`: Test M (Oversized and excess page count limits) — **PASS**
- `tests/test_document_agents_integration.py`: Test N (Document and Vision agent integration) — **PASS**
- `tests/test_end_to_end_scanned_document.py`: Test O (End-to-end scanned PDF pipeline) — **PASS**
- `tests/acceptance/test_phase_6_acceptance.py`: Comprehensive acceptance test suite — **PASS**

**Full Regression Suite**: 273 passed, 1 skipped, 0 failed across Phases 0–6.

---

## 18. Known Limitations
1. **Specialized Engineering Drawing Semantics**: Title block parsing, dimensional tolerance extraction, and CAD symbol semantics are reserved for Phase 7.
2. **Persistent Vector RAG Indexing**: Persistent embeddings and hybrid Qdrant search over evidence objects will be implemented in Phase 8.

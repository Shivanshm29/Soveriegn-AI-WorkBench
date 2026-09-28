"""Main multimodal document understanding pipeline orchestrating all ingestion and analysis stages."""

import os
import uuid
from typing import Dict, Any, List, Optional

from backend.app.multimodal.schemas import (
    DocumentInput,
    DocumentType,
    DocumentTypeResult,
    DocumentEvidence,
    EvidenceType,
    DocumentAnalysisResult,
    OCRBlock,
    RenderedPage,
)
from backend.app.multimodal.errors import (
    DocumentProcessingError,
    UnsupportedDocumentError,
    InvalidPDFError,
    OCRError,
)
from backend.app.multimodal.type_detector import DocumentTypeDetector
from backend.app.multimodal.pdf_processor import PDFProcessor
from backend.app.multimodal.ocr_engine import LocalOCREngine
from backend.app.multimodal.layout_analyzer import LayoutAnalyzer
from backend.app.multimodal.vlm_adapter import VLMDocumentAdapter
from backend.app.multimodal.prompt_defense import PromptInjectionDefense
from backend.app.multimodal.cache import DocumentCache


class MultimodalDocumentPipeline:
    """Coordinating pipeline for deterministic local multimodal document processing."""

    def __init__(
        self,
        pdf_processor: Optional[PDFProcessor] = None,
        ocr_engine: Optional[LocalOCREngine] = None,
        vlm_adapter: Optional[VLMDocumentAdapter] = None,
        cache: Optional[DocumentCache] = None,
    ):
        self.type_detector = DocumentTypeDetector()
        self.pdf_processor = pdf_processor or PDFProcessor()
        self.ocr_engine = ocr_engine or LocalOCREngine()
        self.layout_analyzer = LayoutAnalyzer()
        self.vlm_adapter = vlm_adapter
        self.cache = cache or DocumentCache()

    def process(
        self,
        document_input: DocumentInput,
        enable_vlm: bool = True,
        vlm_query: Optional[str] = None,
    ) -> DocumentAnalysisResult:
        """Run the end-to-end local multimodal document pipeline."""
        warnings: List[str] = []

        # 1. Resource Limits Validation
        self.pdf_processor.validate_limits(document_input)

        # 2. Document Type Detection
        type_result: DocumentTypeResult = self.type_detector.detect(document_input)
        if type_result.detected_type == DocumentType.UNSUPPORTED:
            raise UnsupportedDocumentError(
                f"File '{document_input.filename}' has unsupported structure: {type_result.details.get('reason')}",
                details=type_result.details,
            )

        all_evidence: List[DocumentEvidence] = []
        confidences: List[float] = []

        # Check Cache
        cached_evidence = self.cache.get(
            source_hash=document_input.source_hash,
            page_number=0,  # 0 indicates full document evidence set
            extraction_method="pipeline_full",
        )
        if cached_evidence is not None:
            # Reconstruct result from cache
            for ev in cached_evidence:
                if ev.confidence is not None:
                    confidences.append(ev.confidence)
            return DocumentAnalysisResult(
                document_id=document_input.document_id,
                source_hash=document_input.source_hash,
                document_type=type_result.detected_type,
                page_count=type_result.page_count,
                evidence=cached_evidence,
                warnings=["Retrieved from cryptographic source_hash cache."],
                processing_metadata={"cached": True, "detection": type_result.model_dump()},
                confidence_summary={
                    "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 1.0,
                    "evidence_count": len(cached_evidence),
                },
            )

        # 3. Processing based on detected document type
        if type_result.detected_type == DocumentType.TEXT_PDF:
            # Digital Text PDF
            text_blocks = self.pdf_processor.extract_text_blocks(document_input)
            table_blocks = self.pdf_processor.extract_tables(document_input)
            image_blocks = self.pdf_processor.extract_images(document_input)

            # Convert text blocks to evidence
            for b in text_blocks:
                all_evidence.append(
                    DocumentEvidence(
                        evidence_id=str(uuid.uuid4()),
                        document_id=document_input.document_id,
                        source_hash=document_input.source_hash,
                        page_number=b.page_number,
                        evidence_type=EvidenceType.TEXT,
                        text=b.text,
                        bounding_box=b.bounding_box,
                        confidence=b.confidence,
                        extraction_method=b.extraction_method,
                    )
                )
                confidences.append(b.confidence)

            # Convert tables to evidence
            for t in table_blocks:
                all_evidence.append(
                    DocumentEvidence(
                        evidence_id=str(uuid.uuid4()),
                        document_id=document_input.document_id,
                        source_hash=document_input.source_hash,
                        page_number=t.page_number,
                        evidence_type=EvidenceType.TABLE,
                        text=f"Headers: {t.headers} | Rows: {len(t.rows)}",
                        bounding_box=t.bounding_box,
                        confidence=t.confidence,
                        extraction_method="pymupdf_table",
                        metadata={"headers": t.headers, "rows": t.rows},
                    )
                )
                confidences.append(t.confidence)

            # Convert images to evidence
            for img in image_blocks:
                all_evidence.append(
                    DocumentEvidence(
                        evidence_id=str(uuid.uuid4()),
                        document_id=document_input.document_id,
                        source_hash=document_input.source_hash,
                        page_number=img.page_number,
                        evidence_type=EvidenceType.IMAGE,
                        text=img.image_reference,
                        bounding_box=img.bounding_box,
                        confidence=img.confidence,
                        extraction_method="pymupdf_image",
                        source_reference=img.image_reference,
                    )
                )
                confidences.append(img.confidence)

            # Layout regions
            for p in range(1, type_result.page_count + 1):
                regions = self.layout_analyzer.analyze_page(
                    page_number=p,
                    ocr_blocks=text_blocks,
                    table_blocks=table_blocks,
                    image_blocks=image_blocks,
                    source_hash=document_input.source_hash,
                )
                for r in regions:
                    all_evidence.append(
                        DocumentEvidence(
                            evidence_id=str(uuid.uuid4()),
                            document_id=document_input.document_id,
                            source_hash=document_input.source_hash,
                            page_number=p,
                            evidence_type=EvidenceType.LAYOUT_REGION,
                            text=r.content,
                            bounding_box=r.bounding_box,
                            confidence=r.confidence,
                            extraction_method="layout_analyzer",
                            metadata={"region_type": r.region_type},
                        )
                    )

            # Optional VLM inspection for pages with visual figures/images
            if enable_vlm and self.vlm_adapter and (image_blocks or table_blocks):
                for p in range(1, min(type_result.page_count + 1, 6)):  # Limit VLM inspect to first 5 pages for efficiency
                    rendered = self.pdf_processor.render_page(document_input, p)
                    vlm_ev = self.vlm_adapter.analyze_visual_page(
                        rendered_page=rendered,
                        ocr_blocks=[b for b in text_blocks if b.page_number == p],
                        query=vlm_query,
                    )
                    all_evidence.append(vlm_ev)
                    if vlm_ev.confidence is not None:
                        confidences.append(vlm_ev.confidence)

        elif type_result.detected_type in [DocumentType.SCANNED_PDF, DocumentType.IMAGE_PDF]:
            # Scanned / Image-only PDF -> Local Rendering + OCR
            rendered_pages = self.pdf_processor.render_all_pages(document_input)
            for page in rendered_pages:
                ocr_blocks = self.ocr_engine.process_rendered_page(page)
                for b in ocr_blocks:
                    all_evidence.append(
                        DocumentEvidence(
                            evidence_id=str(uuid.uuid4()),
                            document_id=document_input.document_id,
                            source_hash=document_input.source_hash,
                            page_number=page.page_number,
                            evidence_type=EvidenceType.OCR_TEXT,
                            text=b.text,
                            bounding_box=b.bounding_box,
                            confidence=b.confidence,
                            extraction_method=b.extraction_method,
                        )
                    )
                    confidences.append(b.confidence)

                # Layout regions for scanned page
                regions = self.layout_analyzer.analyze_page(
                    page_number=page.page_number,
                    ocr_blocks=ocr_blocks,
                    source_hash=document_input.source_hash,
                )
                for r in regions:
                    all_evidence.append(
                        DocumentEvidence(
                            evidence_id=str(uuid.uuid4()),
                            document_id=document_input.document_id,
                            source_hash=document_input.source_hash,
                            page_number=page.page_number,
                            evidence_type=EvidenceType.LAYOUT_REGION,
                            text=r.content,
                            bounding_box=r.bounding_box,
                            confidence=r.confidence,
                            extraction_method="layout_analyzer",
                            metadata={"region_type": r.region_type},
                        )
                    )

                # VLM visual observation
                if enable_vlm and self.vlm_adapter:
                    vlm_ev = self.vlm_adapter.analyze_visual_page(
                        rendered_page=page,
                        ocr_blocks=ocr_blocks,
                        query=vlm_query,
                    )
                    all_evidence.append(vlm_ev)
                    if vlm_ev.confidence is not None:
                        confidences.append(vlm_ev.confidence)

        elif type_result.detected_type == DocumentType.IMAGE:
            # Standalone image file
            from PIL import Image
            img = Image.open(document_input.source_path)
            rendered_page = RenderedPage(
                document_id=document_input.document_id,
                source_hash=document_input.source_hash,
                page_number=1,
                width=img.width,
                height=img.height,
                image_path=document_input.source_path,
            )
            ocr_blocks = self.ocr_engine.process_rendered_page(rendered_page)
            for b in ocr_blocks:
                all_evidence.append(
                    DocumentEvidence(
                        evidence_id=str(uuid.uuid4()),
                        document_id=document_input.document_id,
                        source_hash=document_input.source_hash,
                        page_number=1,
                        evidence_type=EvidenceType.OCR_TEXT,
                        text=b.text,
                        bounding_box=b.bounding_box,
                        confidence=b.confidence,
                        extraction_method=b.extraction_method,
                    )
                )
                confidences.append(b.confidence)

            if enable_vlm and self.vlm_adapter:
                vlm_ev = self.vlm_adapter.analyze_visual_page(
                    rendered_page=rendered_page,
                    ocr_blocks=ocr_blocks,
                    query=vlm_query,
                )
                all_evidence.append(vlm_ev)
                if vlm_ev.confidence is not None:
                    confidences.append(vlm_ev.confidence)

        # 4. Prompt Injection Defense Scan
        for ev in all_evidence:
            if ev.text:
                is_safe, flags = PromptInjectionDefense.validate_content_safety(ev.text)
                if not is_safe:
                    warning_msg = f"Security: Prompt injection pattern detected in page {ev.page_number} ({flags}). Content strictly isolated as DATA."
                    if warning_msg not in warnings:
                        warnings.append(warning_msg)
                    # Quarantined data wrapping
                    ev.metadata["injection_flagged"] = True
                    ev.metadata["detected_patterns"] = flags
                    ev.text = PromptInjectionDefense.wrap_document_data(
                        ev.text, document_id=document_input.document_id, page_number=ev.page_number
                    )

        # 5. Save to Cache
        self.cache.put(
            source_hash=document_input.source_hash,
            page_number=0,
            extraction_method="pipeline_full",
            evidence=all_evidence,
        )

        confidence_summary = {
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 1.0,
            "min_confidence": min(confidences) if confidences else 1.0,
            "evidence_count": len(all_evidence),
        }

        return DocumentAnalysisResult(
            document_id=document_input.document_id,
            source_hash=document_input.source_hash,
            document_type=type_result.detected_type,
            page_count=type_result.page_count,
            evidence=all_evidence,
            warnings=warnings,
            processing_metadata={
                "detection": type_result.model_dump(),
                "cached": False,
            },
            confidence_summary=confidence_summary,
        )

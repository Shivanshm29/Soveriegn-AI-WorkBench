"""Document type detection module based on structural inspection."""

import os
from typing import Optional
import pymupdf
from PIL import Image

from backend.app.multimodal.schemas import DocumentInput, DocumentType, DocumentTypeResult
from backend.app.multimodal.errors import InvalidPDFError, UnsupportedDocumentError


class DocumentTypeDetector:
    """Detects document types by deep inspection of structural content rather than extensions alone."""

    @staticmethod
    def detect(document_input: DocumentInput) -> DocumentTypeResult:
        """Inspect the source file and return structured DocumentTypeResult."""
        file_path = document_input.source_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # 1. Inspect magic bytes
        with open(file_path, "rb") as f:
            header = f.read(16)

        # Check for PDF magic header (%PDF-)
        if header.startswith(b"%PDF"):
            return DocumentTypeDetector._inspect_pdf(document_input)

        # Check for Image magic headers (PNG, JPEG, TIFF, BMP, WebP)
        if (
            header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"GIF8")
            or header.startswith(b"BM")
            or (header.startswith(b"RIFF") and b"WEBP" in header)
            or header.startswith(b"MM\x00*")
            or header.startswith(b"II*\x00")
        ):
            return DocumentTypeDetector._inspect_image(document_input)

        # Try opening with PIL as an image fallback
        try:
            with Image.open(file_path) as img:
                img.verify()
            return DocumentTypeDetector._inspect_image(document_input)
        except Exception:
            pass

        # Try opening with pymupdf as fallback
        try:
            doc = pymupdf.open(file_path)
            doc.close()
            return DocumentTypeDetector._inspect_pdf(document_input)
        except Exception:
            pass

        return DocumentTypeResult(
            document_id=document_input.document_id,
            detected_type=DocumentType.UNSUPPORTED,
            page_count=0,
            has_extractable_text=False,
            has_images=False,
            detection_method="magic_bytes_inspection",
            confidence=0.0,
            details={"reason": "File does not match supported PDF or Image signatures."},
        )

    @staticmethod
    def _inspect_pdf(document_input: DocumentInput) -> DocumentTypeResult:
        file_path = document_input.source_path
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            raise InvalidPDFError(f"Failed to open PDF document: {e}") from e

        try:
            page_count = len(doc)
            if page_count == 0:
                return DocumentTypeResult(
                    document_id=document_input.document_id,
                    detected_type=DocumentType.UNSUPPORTED,
                    page_count=0,
                    has_extractable_text=False,
                    has_images=False,
                    detection_method="pdf_structural_inspection",
                    confidence=0.0,
                    details={"reason": "PDF contains zero pages."},
                )

            total_text_length = 0
            has_images = False
            pages_with_text = 0

            for page in doc:
                text = page.get_text().strip()
                if len(text) > 20:
                    pages_with_text += 1
                total_text_length += len(text)

                images = page.get_images()
                if images:
                    has_images = True

            has_extractable_text = total_text_length > 40 or pages_with_text > 0

            if has_extractable_text:
                detected_type = DocumentType.TEXT_PDF
            elif has_images:
                # Scanned or image-based PDF
                detected_type = DocumentType.SCANNED_PDF
            else:
                # No text, no images (e.g. empty or vector drawing)
                detected_type = DocumentType.IMAGE_PDF

            return DocumentTypeResult(
                document_id=document_input.document_id,
                detected_type=detected_type,
                page_count=page_count,
                has_extractable_text=has_extractable_text,
                has_images=has_images,
                detection_method="pdf_structural_inspection",
                confidence=1.0,
                details={
                    "total_text_chars": total_text_length,
                    "pages_with_text": pages_with_text,
                    "has_images": has_images,
                },
            )
        finally:
            doc.close()

    @staticmethod
    def _inspect_image(document_input: DocumentInput) -> DocumentTypeResult:
        file_path = document_input.source_path
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                img_format = img.format
            return DocumentTypeResult(
                document_id=document_input.document_id,
                detected_type=DocumentType.IMAGE,
                page_count=1,
                has_extractable_text=False,
                has_images=True,
                detection_method="image_header_inspection",
                confidence=1.0,
                details={"width": width, "height": height, "format": img_format},
            )
        except Exception as e:
            raise UnsupportedDocumentError(f"Corrupted or invalid image file: {e}") from e

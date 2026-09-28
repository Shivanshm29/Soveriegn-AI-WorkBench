"""Local PDF processing module utilizing PyMuPDF for text extraction, rendering, tables, and images."""

import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
import pymupdf

from backend.app.multimodal.schemas import (
    DocumentInput,
    RenderedPage,
    OCRBlock,
    TableBlock,
    ImageBlock,
)
from backend.app.multimodal.errors import (
    InvalidPDFError,
    UnreadablePageError,
    DocumentTooLargeError,
    PageLimitExceededError,
    RenderingError,
)

DEFAULT_CACHE_DIR = os.path.abspath(os.path.join("data", "cache", "rendered_pages"))


class PDFProcessor:
    """Handles local PDF parsing, rendering, text/table/image extraction, and resource limits."""

    def __init__(
        self,
        max_file_size_bytes: int = 50 * 1024 * 1024,  # 50 MB
        max_page_count: int = 100,
        render_dpi: int = 150,
        cache_dir: str = DEFAULT_CACHE_DIR,
    ):
        self.max_file_size_bytes = max_file_size_bytes
        self.max_page_count = max_page_count
        self.render_dpi = render_dpi
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def validate_limits(self, document_input: DocumentInput) -> None:
        """Check file size and resource limits before reading."""
        if document_input.file_size > self.max_file_size_bytes:
            raise DocumentTooLargeError(
                f"Document size ({document_input.file_size} bytes) exceeds limit ({self.max_file_size_bytes} bytes).",
                file_size=document_input.file_size,
                max_allowed=self.max_file_size_bytes,
            )

    def open_doc(self, file_path: str) -> pymupdf.Document:
        """Open PDF document safely, handling corrupted or invalid files."""
        try:
            doc = pymupdf.open(file_path)
            if len(doc) > self.max_page_count:
                page_count = len(doc)
                doc.close()
                raise PageLimitExceededError(
                    f"Document page count ({page_count}) exceeds limit ({self.max_page_count}).",
                    page_count=page_count,
                    max_allowed=self.max_page_count,
                )
            return doc
        except (DocumentTooLargeError, PageLimitExceededError):
            raise
        except Exception as e:
            raise InvalidPDFError(f"Failed to open PDF document at {file_path}: {e}") from e

    def extract_text_blocks(self, document_input: DocumentInput) -> List[OCRBlock]:
        """Extract native text blocks from all pages with bounding boxes and confidence."""
        self.validate_limits(document_input)
        doc = self.open_doc(document_input.source_path)
        blocks: List[OCRBlock] = []

        try:
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                try:
                    # get_text("blocks") returns tuples: (x0, y0, x1, y1, text, block_no, block_type)
                    # block_type 0 is text, 1 is image
                    raw_blocks = page.get_text("blocks")
                    for b in raw_blocks:
                        if len(b) >= 5 and b[4].strip():
                            text_content = b[4].strip()
                            bbox = [round(float(b[0]), 2), round(float(b[1]), 2), round(float(b[2]), 2), round(float(b[3]), 2)]
                            blocks.append(
                                OCRBlock(
                                    block_id=str(uuid.uuid4()),
                                    page_number=page_num,
                                    text=text_content,
                                    confidence=1.0,  # Native digital PDF text is 100% confident
                                    bounding_box=bbox,
                                    source_hash=document_input.source_hash,
                                    extraction_method="native_text",
                                )
                            )
                except Exception as e:
                    raise UnreadablePageError(
                        f"Failed to read text on page {page_num}: {e}",
                        page_number=page_num,
                    ) from e
        finally:
            doc.close()

        return blocks

    def render_page(self, document_input: DocumentInput, page_number: int) -> RenderedPage:
        """Render a single page (1-indexed) to an image file in the local cache."""
        self.validate_limits(document_input)
        doc = self.open_doc(document_input.source_path)

        try:
            if page_number < 1 or page_number > len(doc):
                raise UnreadablePageError(
                    f"Requested page {page_number} is out of bounds (1..{len(doc)}).",
                    page_number=page_number,
                )

            page = doc[page_number - 1]
            zoom = self.render_dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            filename = f"{document_input.source_hash}_p{page_number}_{self.render_dpi}dpi.png"
            output_path = os.path.join(self.cache_dir, filename)
            pix.save(output_path)

            return RenderedPage(
                document_id=document_input.document_id,
                source_hash=document_input.source_hash,
                page_number=page_number,
                width=pix.width,
                height=pix.height,
                image_path=output_path,
                format="png",
                dpi=self.render_dpi,
            )
        except UnreadablePageError:
            raise
        except Exception as e:
            raise RenderingError(
                f"Failed to render page {page_number}: {e}",
                page_number=page_number,
            ) from e
        finally:
            doc.close()

    def render_all_pages(self, document_input: DocumentInput) -> List[RenderedPage]:
        """Render all pages of the document."""
        self.validate_limits(document_input)
        doc = self.open_doc(document_input.source_path)
        rendered: List[RenderedPage] = []
        page_count = len(doc)
        doc.close()

        for p in range(1, page_count + 1):
            rendered.append(self.render_page(document_input, p))
        return rendered

    def extract_tables(self, document_input: DocumentInput) -> List[TableBlock]:
        """Detect and extract tabular structures across pages without hallucinating cells."""
        self.validate_limits(document_input)
        doc = self.open_doc(document_input.source_path)
        tables: List[TableBlock] = []

        try:
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                try:
                    tabs = page.find_tables()
                    for tab in tabs:
                        bbox = [
                            round(float(tab.bbox[0]), 2),
                            round(float(tab.bbox[1]), 2),
                            round(float(tab.bbox[2]), 2),
                            round(float(tab.bbox[3]), 2),
                        ]
                        extracted_data = tab.extract()
                        if not extracted_data:
                            continue

                        headers = [str(cell or "").strip() for cell in extracted_data[0]] if extracted_data else []
                        rows = [
                            [str(cell or "").strip() for cell in row]
                            for row in extracted_data[1:]
                        ] if len(extracted_data) > 1 else []

                        tables.append(
                            TableBlock(
                                table_id=str(uuid.uuid4()),
                                page_number=page_num,
                                bounding_box=bbox,
                                rows=rows,
                                headers=headers,
                                confidence=0.95,
                                source_hash=document_input.source_hash,
                            )
                        )
                except Exception as e:
                    # Non-fatal per-page table extraction issue
                    continue
        finally:
            doc.close()

        return tables

    def extract_images(self, document_input: DocumentInput) -> List[ImageBlock]:
        """Identify embedded images on each page and extract their coordinates."""
        self.validate_limits(document_input)
        doc = self.open_doc(document_input.source_path)
        images: List[ImageBlock] = []

        try:
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                image_list = page.get_images()
                for img_info in image_list:
                    xref = img_info[0]
                    try:
                        bbox_rect = page.get_image_bbox(img_info)
                        bbox = [
                            round(float(bbox_rect.x0), 2),
                            round(float(bbox_rect.y0), 2),
                            round(float(bbox_rect.x1), 2),
                            round(float(bbox_rect.y1), 2),
                        ]
                    except Exception:
                        bbox = [0.0, 0.0, 0.0, 0.0]

                    image_ref = f"xref_{xref}_p{page_num}"
                    images.append(
                        ImageBlock(
                            image_id=str(uuid.uuid4()),
                            page_number=page_num,
                            bounding_box=bbox,
                            source_hash=document_input.source_hash,
                            image_reference=image_ref,
                            extraction_method="pymupdf",
                            confidence=1.0,
                        )
                    )
        finally:
            doc.close()

        return images

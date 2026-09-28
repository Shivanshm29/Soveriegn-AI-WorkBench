"""Document layout analysis module categorizing structural regions."""

import re
import uuid
from typing import List, Optional

from backend.app.multimodal.schemas import (
    OCRBlock,
    TableBlock,
    ImageBlock,
    LayoutRegion,
)


class LayoutAnalyzer:
    """Analyzes spatial and structural relationships across document pages."""

    @staticmethod
    def analyze_page(
        page_number: int,
        ocr_blocks: List[OCRBlock],
        table_blocks: Optional[List[TableBlock]] = None,
        image_blocks: Optional[List[ImageBlock]] = None,
        source_hash: str = "",
    ) -> List[LayoutRegion]:
        """Categorize page layout into paragraphs, headings, tables, figures, images, lists, captions."""
        regions: List[LayoutRegion] = []
        page_tables = [t for t in (table_blocks or []) if t.page_number == page_number]
        page_images = [img for img in (image_blocks or []) if img.page_number == page_number]
        page_ocr = [b for b in ocr_blocks if b.page_number == page_number]

        # 1. Register Table regions
        for table in page_tables:
            regions.append(
                LayoutRegion(
                    region_id=str(uuid.uuid4()),
                    page_number=page_number,
                    region_type="table",
                    bounding_box=table.bounding_box,
                    confidence=table.confidence,
                    content=f"Table with {len(table.rows)} rows",
                    source_hash=source_hash,
                )
            )

        # 2. Register Image / Figure regions
        for img in page_images:
            reg_type = "figure" if "diagram" in img.image_reference.lower() or "fig" in img.image_reference.lower() else "image"
            regions.append(
                LayoutRegion(
                    region_id=str(uuid.uuid4()),
                    page_number=page_number,
                    region_type=reg_type,
                    bounding_box=img.bounding_box,
                    confidence=img.confidence,
                    content=img.image_reference,
                    source_hash=source_hash,
                )
            )

        # 3. Analyze text blocks for headings, lists, captions, paragraphs, handwriting
        for b in page_ocr:
            text = b.text.strip()
            if not text:
                continue

            # Check if block is inside a table region (avoid duplicate region if fully contained)
            is_inside_table = False
            for t in page_tables:
                tb = t.bounding_box
                bb = b.bounding_box
                if tb[0] <= bb[0] and tb[1] <= bb[1] and tb[2] >= bb[2] and tb[3] >= bb[3]:
                    is_inside_table = True
                    break
            if is_inside_table:
                continue

            region_type = LayoutAnalyzer._classify_text_block(text, b)
            regions.append(
                LayoutRegion(
                    region_id=str(uuid.uuid4()),
                    page_number=page_number,
                    region_type=region_type,
                    bounding_box=b.bounding_box,
                    confidence=b.confidence,
                    content=text,
                    source_hash=source_hash,
                )
            )

        return regions

    @staticmethod
    def _classify_text_block(text: str, block: OCRBlock) -> str:
        """Classify a text block based on heuristics, structure, and metadata."""
        # Handwriting check (marked via extraction method or low confidence visual marker)
        if "handwriting" in block.extraction_method.lower() or "[handwritten]" in text.lower():
            return "handwritten_region"

        # Caption check
        if re.match(r"^(Figure|Fig\.|Table|Exhibit)\s+\d+[:\.-]", text, re.IGNORECASE):
            return "caption"

        # List item check
        if re.match(r"^([\u2022\u25cf\-\*]|\d+[\.\)])\s+", text):
            return "list"

        # Heading check: Short, uppercase or title case, or numbered section
        is_short = len(text) < 80
        is_numbered_section = bool(re.match(r"^(\d+\.){1,3}\s+[A-Z]", text))
        is_all_caps = text.isupper() and len(text.split()) < 10

        if is_short and (is_numbered_section or is_all_caps or text.endswith(":")):
            return "heading"

        return "paragraph"

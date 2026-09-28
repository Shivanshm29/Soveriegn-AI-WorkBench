"""Visual region detector for engineering drawings and industrial visual artifacts."""

import re
import uuid
from typing import List, Optional, Tuple
from PIL import Image

from backend.app.multimodal.schemas import OCRBlock
from backend.app.vision.schemas import VisualRegion, ConfidenceAssessment, ConfidenceLevel


class VisualRegionDetector:
    """Classifies regions in engineering drawings and industrial images into structured visual areas."""

    TITLE_BLOCK_KEYWORDS = {
        "dwg", "drawing", "title", "scale", "sheet", "rev", "revision", "approved",
        "date", "material", "drawn", "checked", "tolerance", "projection", "engineer"
    }

    DIMENSION_REGEX = re.compile(
        r"(?:(?:R|DIA|⌀|Ø)\s*)?\d+(?:\.\d+)?\s*(?:mm|in|cm|deg|°|µm)?(?:\s*(?:±|\+/-)\s*\d+(?:\.\d+)?)?",
        re.IGNORECASE,
    )

    @classmethod
    def detect_regions(
        cls,
        image_path: Optional[str] = None,
        image: Optional[Image.Image] = None,
        ocr_blocks: Optional[List[Any]] = None,
        source_hash: str = "",
        page_number: int = 1,
    ) -> List[VisualRegion]:
        """Detect and classify regions on an engineering drawing or inspection image."""
        if image is not None:
            width, height = image.size
        elif image_path:
            with Image.open(image_path) as img:
                width, height = img.size
        else:
            width, height = 800, 600

        regions: List[VisualRegion] = []
        raw_blocks = ocr_blocks or []
        blocks: List[OCRBlock] = []

        for b in raw_blocks:
            if isinstance(b, dict):
                bbox = b.get("bounding_box") or b.get("bbox", [0.0, 0.0, 0.0, 0.0])
                text = b.get("text", "")
                conf = b.get("confidence", 0.9)
                blocks.append(
                    OCRBlock(
                        block_id=str(uuid.uuid4()),
                        page_number=page_number,
                        text=text,
                        confidence=conf,
                        bounding_box=bbox,
                        source_hash=source_hash,
                        extraction_method="normalized",
                    )
                )
            else:
                blocks.append(b)

        # 1. Identify Title Block via geometry and keyword presence
        title_block_blocks = []
        notes_blocks = []
        dimension_blocks = []
        callout_blocks = []

        for b in blocks:
            text_lower = b.text.lower()
            x0, y0, x1, y1 = b.bounding_box

            # Check if in standard bottom-right/bottom quadrant for Title Block
            in_title_quadrant = (x0 >= 0.50 * width) and (y0 >= 0.65 * height)
            has_title_kw = any(kw in text_lower for kw in cls.TITLE_BLOCK_KEYWORDS)

            if in_title_quadrant or has_title_kw:
                title_block_blocks.append(b)
            elif "note" in text_lower or text_lower.startswith(("general notes", "notes:")):
                notes_blocks.append(b)
            elif cls.is_dimension_text(b.text):
                dimension_blocks.append(b)
            elif any(prefix in text_lower for prefix in ("section", "detail", "view", "item", "part")):
                callout_blocks.append(b)

        # Build Title Block Region if detected
        if title_block_blocks:
            min_x = min(b.bounding_box[0] for b in title_block_blocks)
            min_y = min(b.bounding_box[1] for b in title_block_blocks)
            max_x = max(b.bounding_box[2] for b in title_block_blocks)
            max_y = max(b.bounding_box[3] for b in title_block_blocks)

            # Ensure minimal title block bounds
            min_x = max(0.0, min_x - 10)
            min_y = max(0.0, min_y - 10)
            max_x = min(float(width), max_x + 10)
            max_y = min(float(height), max_y + 10)

            title_text = " | ".join(b.text for b in title_block_blocks)
            regions.append(
                VisualRegion(
                    region_id=f"reg_title_{uuid.uuid4().hex[:6]}",
                    page_number=page_number,
                    region_type="title_block",
                    bounding_box=[round(min_x, 1), round(min_y, 1), round(max_x, 1), round(max_y, 1)],
                    confidence=ConfidenceAssessment.from_score(0.92, "Detected title block via positional heuristics and metadata keywords."),
                    source_hash=source_hash,
                    text_content=title_text,
                    sub_elements=[b.block_id for b in title_block_blocks],
                )
            )
        elif width >= 600 and height >= 400:
            # Standard geometric placement candidate for engineering drawing title block (ISO 7200 / ASME)
            tb_x0 = round(width * 0.65, 1)
            tb_y0 = round(height * 0.80, 1)
            tb_x1 = round(width - 20.0, 1)
            tb_y1 = round(height - 20.0, 1)
            regions.append(
                VisualRegion(
                    region_id=f"reg_title_{uuid.uuid4().hex[:6]}",
                    page_number=page_number,
                    region_type="title_block",
                    bounding_box=[tb_x0, tb_y0, tb_x1, tb_y1],
                    confidence=ConfidenceAssessment.from_score(0.78, "Standard bottom-right geometric placement candidate."),
                    source_hash=source_hash,
                    text_content=None,
                    sub_elements=[],
                )
            )

        # Build Notes Region if detected
        if notes_blocks:
            min_x = min(b.bounding_box[0] for b in notes_blocks)
            min_y = min(b.bounding_box[1] for b in notes_blocks)
            max_x = max(b.bounding_box[2] for b in notes_blocks)
            max_y = max(b.bounding_box[3] for b in notes_blocks)
            regions.append(
                VisualRegion(
                    region_id=f"reg_notes_{uuid.uuid4().hex[:6]}",
                    page_number=page_number,
                    region_type="notes",
                    bounding_box=[round(min_x, 1), round(min_y, 1), round(max_x, 1), round(max_y, 1)],
                    confidence=ConfidenceAssessment.from_score(0.88, "Identified engineering drawing general notes block."),
                    source_hash=source_hash,
                    text_content="\n".join(b.text for b in notes_blocks),
                    sub_elements=[b.block_id for b in notes_blocks],
                )
            )

        # Build Dimensions Regions
        for db in dimension_blocks:
            regions.append(
                VisualRegion(
                    region_id=f"reg_dim_{uuid.uuid4().hex[:6]}",
                    page_number=page_number,
                    region_type="dimensions",
                    bounding_box=db.bounding_box,
                    confidence=ConfidenceAssessment.from_score(db.confidence, "Dimensional callout matching engineering unit pattern."),
                    source_hash=source_hash,
                    text_content=db.text,
                    sub_elements=[db.block_id],
                )
            )

        # Build Callout / Section Regions
        for cb in callout_blocks:
            regions.append(
                VisualRegion(
                    region_id=f"reg_callout_{uuid.uuid4().hex[:6]}",
                    page_number=page_number,
                    region_type="callouts",
                    bounding_box=cb.bounding_box,
                    confidence=ConfidenceAssessment.from_score(cb.confidence, "Engineering view / detail callout label."),
                    source_hash=source_hash,
                    text_content=cb.text,
                    sub_elements=[cb.block_id],
                )
            )

        # Drawing Body (Center visual area)
        body_box = [round(0.05 * width, 1), round(0.05 * height, 1), round(0.95 * width, 1), round(0.85 * height, 1)]
        regions.append(
            VisualRegion(
                region_id=f"reg_body_{uuid.uuid4().hex[:6]}",
                page_number=page_number,
                region_type="drawing_body",
                bounding_box=body_box,
                confidence=ConfidenceAssessment.from_score(0.85, "Primary graphical drawing geometry viewport."),
                source_hash=source_hash,
                text_content=None,
            )
        )

        return regions

    @classmethod
    def is_dimension_text(cls, text: str) -> bool:
        """Check if text conforms to dimensional and tolerance notation."""
        cleaned = text.strip()
        # Look for digits combined with common dimensional indicators
        if any(indicator in cleaned for indicator in ("mm", "in", "cm", "deg", "°", "±", "⌀", "Ø", "DIA", "R")):
            return True
        # Match isolated dimension numbers like 25.4 or 100
        if re.match(r"^\d+(?:\.\d+)?(?:\s*(?:±|\+/-)\s*\d+(?:\.\d+)?)?$", cleaned):
            return True
        return False

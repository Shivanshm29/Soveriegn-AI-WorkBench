"""Multimodal document tools integrated into the authoritative ToolRegistry."""

from typing import List
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry


def get_multimodal_tools() -> List[ToolContract]:
    """Define standard Phase 6 multimodal document processing tools."""
    return [
        ToolContract(
            tool_id="document_type_detect",
            name="Document Type Detector",
            description="Inspects file signatures and layout to distinguish text, scanned, or image PDFs and images.",
            capabilities=["document_type_detection", "pdf_ingestion"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"source_path": {"type": "string"}}, "required": ["source_path"]},
            output_schema={"type": "object", "properties": {"detected_type": {"type": "string"}, "page_count": {"type": "integer"}}},
        ),
        ToolContract(
            tool_id="pdf_text_extract",
            name="PDF Native Text Extractor",
            description="Extracts digital text and spatial bounding boxes from PDF documents.",
            capabilities=["pdf_text_extraction", "page_extraction", "document_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"source_path": {"type": "string"}}, "required": ["source_path"]},
            output_schema={"type": "object", "properties": {"blocks": {"type": "array"}}},
        ),
        ToolContract(
            tool_id="pdf_render",
            name="PDF Page Renderer",
            description="Renders PDF pages to high-resolution local raster images for visual and OCR processing.",
            capabilities=["pdf_rendering", "page_rendering"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"source_path": {"type": "string"}, "page_number": {"type": "integer"}}, "required": ["source_path"]},
            output_schema={"type": "object", "properties": {"image_path": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}}},
        ),
        ToolContract(
            tool_id="layout_analyze",
            name="Document Layout Analyzer",
            description="Identifies headings, paragraphs, tables, images, and captions across document pages.",
            capabilities=["document_structure", "layout_analysis"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"page_number": {"type": "integer"}, "ocr_blocks": {"type": "array"}}},
            output_schema={"type": "object", "properties": {"regions": {"type": "array"}}},
        ),
        ToolContract(
            tool_id="table_extract",
            name="Table Extractor",
            description="Identifies and parses tabular cell boundaries and structured rows from document pages.",
            capabilities=["table_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"source_path": {"type": "string"}}, "required": ["source_path"]},
            output_schema={"type": "object", "properties": {"tables": {"type": "array"}}},
        ),
        ToolContract(
            tool_id="image_extract",
            name="Embedded Image Extractor",
            description="Locates and extracts embedded figures and image artifacts from PDF pages.",
            capabilities=["image_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"source_path": {"type": "string"}}, "required": ["source_path"]},
            output_schema={"type": "object", "properties": {"images": {"type": "array"}}},
        ),
        ToolContract(
            tool_id="vlm_analyze_document",
            name="VLM Document Analyzer",
            description="Applies local Vision-Language Model to perform visual document reasoning on page images.",
            capabilities=["visual_document_understanding", "visual_reasoning", "visual_evidence"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={"type": "object", "properties": {"image_path": {"type": "string"}, "query": {"type": "string"}}, "required": ["image_path"]},
            output_schema={"type": "object", "properties": {"observation": {"type": "string"}, "confidence": {"type": "number"}}},
        ),
    ]


def register_multimodal_tools(registry: ToolRegistry) -> None:
    """Register all Phase 6 multimodal tools into the provided ToolRegistry."""
    for tool in get_multimodal_tools():
        registry.register(tool, overwrite=True)

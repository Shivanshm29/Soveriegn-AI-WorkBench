"""Engineering Drawing and Industrial Vision tools integrated into ToolRegistry."""

from typing import List
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry


def get_vision_tools() -> List[ToolContract]:
    """Define standard Phase 7 engineering drawing and industrial vision tools."""
    return [
        ToolContract(
            tool_id="engineering_drawing_analyze",
            name="Engineering Drawing Analyzer",
            description="Analyzes engineering drawings, technical diagrams, and schematics to extract title blocks, dimensions, notes, and visual evidence.",
            capabilities=["engineering_drawing_analysis", "vision.engineering_analysis", "dimension_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "enable_tiling": {"type": "boolean"},
                    "user_focus": {"type": "string"},
                },
                "required": ["source_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "object"},
                    "status": {"type": "string"},
                },
            },
        ),
        ToolContract(
            tool_id="industrial_image_inspect",
            name="Industrial Photograph Inspector",
            description="Inspects industrial equipment photos for candidate surface discoloration, corrosion candidates, wear, and component indications.",
            capabilities=["industrial_inspection", "vision.image_understanding", "candidate_defect_detection"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "inspection_type": {"type": "string"},
                },
                "required": ["source_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "status": {"type": "string"},
                },
            },
        ),
        ToolContract(
            tool_id="image_preprocess_tile",
            name="Image Preprocessor and Tiler",
            description="Locally normalizes contrast, denoises, and tiles large engineering drawings without quality loss.",
            capabilities=["image_tiling", "image_preprocessing", "region_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "tile_size": {"type": "integer"},
                },
                "required": ["source_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "tiles": {"type": "array"},
                    "tile_count": {"type": "integer"},
                },
            },
        ),
        ToolContract(
            tool_id="visual_region_detect",
            name="Visual Region Detector",
            description="Detects structural layout regions (title blocks, drawing views, dimensions, annotations, notes, diagrams) in engineering drawings.",
            capabilities=["visual_region_detection", "layout_segmentation"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                },
                "required": ["source_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "regions": {"type": "array"},
                },
            },
        ),
        ToolContract(
            tool_id="verify_visual_evidence",
            name="Visual Evidence Verifier",
            description="Deterministically verifies source hashes, bounding boxes, evidence references, and non-certified candidate terminology in vision results.",
            capabilities=["visual_evidence_verification", "deterministic_verification"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
            input_schema={
                "type": "object",
                "properties": {
                    "vision_result": {"type": "object"},
                    "expected_source_hash": {"type": "string"},
                },
                "required": ["vision_result"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "status": {"type": "string"},
                    "details": {"type": "object"},
                },
            },
        ),
    ]


def register_vision_tools(registry: ToolRegistry) -> None:
    """Register all Phase 7 engineering vision tools into the provided ToolRegistry."""
    for tool in get_vision_tools():
        registry.register(tool, overwrite=True)

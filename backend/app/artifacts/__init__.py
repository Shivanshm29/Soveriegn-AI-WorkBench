"""Local Artifact Generation package."""

from backend.app.artifacts.schemas import (
    ArtifactMetadata,
    ApprovalNoteContent,
    SpreadsheetContent,
    SpreadsheetSheetData,
    ArtifactVerificationResult,
)
from backend.app.artifacts.docx_generator import DocxArtifactGenerator
from backend.app.artifacts.xlsx_generator import XlsxArtifactGenerator
from backend.app.artifacts.verifier import ArtifactVerifier
from backend.app.artifacts.factory import ArtifactFactory, get_artifact_factory
from backend.app.artifacts.tools import (
    generate_docx_tool,
    generate_xlsx_tool,
    register_artifact_tools,
)

__all__ = [
    "ArtifactMetadata",
    "ApprovalNoteContent",
    "SpreadsheetContent",
    "SpreadsheetSheetData",
    "ArtifactVerificationResult",
    "DocxArtifactGenerator",
    "XlsxArtifactGenerator",
    "ArtifactVerifier",
    "ArtifactFactory",
    "get_artifact_factory",
    "generate_docx_tool",
    "generate_xlsx_tool",
    "register_artifact_tools",
]

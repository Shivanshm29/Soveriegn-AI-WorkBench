"""Tool declarations and registry integration for create_docx and create_xlsx."""

from typing import Dict, Any, Optional, List
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry
from backend.app.artifacts.schemas import (
    ApprovalNoteContent,
    SpreadsheetContent,
    SpreadsheetSheetData,
)
from backend.app.artifacts.factory import get_artifact_factory


def generate_docx_tool(
    title: str = "Inspection Approval Note",
    summary: str = "",
    equipment_id: Optional[str] = None,
    candidate_findings: Optional[List[Dict[str, Any]]] = None,
    evidence_citations: Optional[List[Dict[str, Any]]] = None,
    recommendations: Optional[List[str]] = None,
    task_id: str = "default_task",
) -> Dict[str, Any]:
    """Tool implementation for generating a verified DOCX report."""
    factory = get_artifact_factory()
    content = ApprovalNoteContent(
        title=title,
        summary=summary,
        equipment_id=equipment_id,
        candidate_findings=candidate_findings or [],
        evidence_citations=evidence_citations or [],
        recommendations=recommendations or [],
    )
    meta = factory.create_approval_note(content, task_id=task_id)
    return meta.to_dict()


def generate_xlsx_tool(
    title: str = "Data Workbook",
    sheets: Optional[List[Dict[str, Any]]] = None,
    task_id: str = "default_task",
) -> Dict[str, Any]:
    """Tool implementation for generating a verified XLSX spreadsheet."""
    factory = get_artifact_factory()
    sheet_objs = []
    for s in (sheets or []):
        sheet_objs.append(
            SpreadsheetSheetData(
                title=s.get("title", "Sheet1"),
                headers=s.get("headers", []),
                rows=s.get("rows", []),
                include_summary_row=s.get("include_summary_row", False),
            )
        )
    if not sheet_objs:
        sheet_objs.append(
            SpreadsheetSheetData(
                title="Data",
                headers=["Metric", "Value"],
                rows=[["Execution", "Completed"]],
            )
        )
    content = SpreadsheetContent(
        title=title,
        sheets=sheet_objs,
        task_id=task_id,
    )
    meta = factory.create_spreadsheet(content)
    return meta.to_dict()


def register_artifact_tools(registry: ToolRegistry) -> None:
    """Register create_docx and create_xlsx tools into ToolRegistry."""
    docx_tool = ToolContract(
        tool_id="create_docx",
        name="DOCX Report Generator",
        description="Compiles structured text, headers, and evidence tables into formatted Word documents.",
        capabilities=["document_generation", "report_export"],
        risk_level="LOW",
        requires_approval=False,
        enabled=True,
    )
    xlsx_tool = ToolContract(
        tool_id="create_xlsx",
        name="XLSX Workbook Generator",
        description="Generates styled spreadsheets with calculated cells and tabular evidence traces.",
        capabilities=["sheet_generation", "data_export"],
        risk_level="LOW",
        requires_approval=False,
        enabled=True,
    )
    registry.register(docx_tool, overwrite=True)
    registry.register(xlsx_tool, overwrite=True)

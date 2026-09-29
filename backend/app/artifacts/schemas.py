"""Schemas for sovereign local artifact generation, metadata, and verification."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    """Authoritative metadata attached to every locally generated artifact."""

    artifact_id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    task_id: str
    artifact_type: Literal["docx", "xlsx", "txt", "json"]
    file_path: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str
    source_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    status: Literal["GENERATED", "VERIFIED", "FAILED"] = "GENERATED"
    file_size_bytes: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return self.model_dump(mode="json")


class ApprovalNoteContent(BaseModel):
    """Structured content for an authoritative engineering inspection approval note."""

    title: str = "Engineering Inspection Approval Note"
    equipment_id: Optional[str] = None
    document_title: Optional[str] = None
    inspector: Optional[str] = None
    summary: str
    candidate_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_citations: List[Dict[str, Any]] = Field(default_factory=list)
    policy_decision: Optional[str] = "ALLOW"
    human_approval: Optional[Dict[str, Any]] = None
    recommendations: List[str] = Field(default_factory=list)
    data_sensitivity: str = "INTERNAL"


class SpreadsheetSheetData(BaseModel):
    """Specification of a sheet inside an XLSX workbook."""

    title: str
    headers: List[str]
    rows: List[List[Any]]
    include_summary_row: bool = False


class SpreadsheetContent(BaseModel):
    """Structured content for generating multi-sheet XLSX workbooks."""

    title: str = "Engineering Data Workbook"
    sheets: List[SpreadsheetSheetData]
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ArtifactVerificationResult(BaseModel):
    """Deterministic verification result for generated artifacts."""

    is_verified: bool
    artifact_id: str
    artifact_type: str
    checks: Dict[str, bool] = Field(default_factory=dict)
    failure_reasons: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert verification result to dictionary."""
        return self.model_dump(mode="json")

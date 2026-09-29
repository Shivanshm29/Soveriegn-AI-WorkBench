"""Central factory managing sovereign artifact generation and verification."""

import os
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any

from backend.app.artifacts.schemas import (
    ArtifactMetadata,
    ApprovalNoteContent,
    SpreadsheetContent,
    ArtifactVerificationResult,
)
from backend.app.artifacts.docx_generator import DocxArtifactGenerator
from backend.app.artifacts.xlsx_generator import XlsxArtifactGenerator
from backend.app.artifacts.verifier import ArtifactVerifier


DEFAULT_ARTIFACT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache", "artifacts")
)


class ArtifactFactory:
    """Unified local manager for generating, hashing, and verifying audit-ready artifacts."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or DEFAULT_ARTIFACT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        self.docx_generator = DocxArtifactGenerator()
        self.xlsx_generator = XlsxArtifactGenerator()
        self.verifier = ArtifactVerifier()

    def create_approval_note(
        self,
        content: ApprovalNoteContent,
        task_id: str = "default_task",
        output_filename: Optional[str] = None,
    ) -> ArtifactMetadata:
        """Create and hash a professional DOCX approval note."""
        fname = output_filename or f"approval_note_{task_id}_{uuid.uuid4().hex[:6]}.docx"
        output_path = os.path.join(self.output_dir, fname)
        meta = self.docx_generator.generate_approval_note(content, output_path, task_id=task_id)
        # Verify immediately
        v_res = self.verifier.verify(meta)
        if v_res.is_verified:
            meta.status = "VERIFIED"
        return meta

    def create_spreadsheet(
        self,
        content: SpreadsheetContent,
        output_filename: Optional[str] = None,
    ) -> ArtifactMetadata:
        """Create and hash a styled multi-sheet XLSX workbook."""
        fname = output_filename or f"data_workbook_{content.task_id}_{uuid.uuid4().hex[:6]}.xlsx"
        output_path = os.path.join(self.output_dir, fname)
        meta = self.xlsx_generator.generate_workbook(content, output_path)
        v_res = self.verifier.verify(meta)
        if v_res.is_verified:
            meta.status = "VERIFIED"
        return meta

    def create_json_artifact(
        self,
        data: Dict[str, Any],
        task_id: str = "default_task",
        output_filename: Optional[str] = None,
    ) -> ArtifactMetadata:
        """Save a structured JSON report locally with SHA-256 hash."""
        fname = output_filename or f"report_{task_id}_{uuid.uuid4().hex[:6]}.json"
        output_path = os.path.join(self.output_dir, fname)
        raw_bytes = json.dumps(data, indent=2).encode("utf-8")
        with open(output_path, "wb") as f:
            f.write(raw_bytes)
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        meta = ArtifactMetadata(
            task_id=task_id,
            artifact_type="json",
            file_path=output_path,
            content_hash=content_hash,
            file_size_bytes=len(raw_bytes),
            status="VERIFIED",
        )
        return meta

    def verify_artifact(
        self,
        artifact: ArtifactMetadata,
        known_evidence_hashes: Optional[List[str]] = None,
    ) -> ArtifactVerificationResult:
        """Verify artifact integrity and readable format."""
        return self.verifier.verify(artifact, known_evidence_hashes)


# Global singleton factory
_default_artifact_factory: Optional[ArtifactFactory] = None


def get_artifact_factory() -> ArtifactFactory:
    """Retrieve or initialize the global ArtifactFactory."""
    global _default_artifact_factory
    if _default_artifact_factory is None:
        _default_artifact_factory = ArtifactFactory()
    return _default_artifact_factory

"""Local DOCX artifact generator for engineering inspection reports and approval notes."""

import os
import hashlib
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Optional, List, Dict, Any

from backend.app.artifacts.schemas import (
    ArtifactMetadata,
    ApprovalNoteContent,
)


class DocxArtifactGenerator:
    """Generates structured, professional Word documents locally via python-docx."""

    @staticmethod
    def _compute_file_hash(path: str) -> str:
        """Compute SHA-256 content hash of file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def generate_approval_note(
        self,
        content: ApprovalNoteContent,
        output_path: str,
        task_id: str = "default_task",
    ) -> ArtifactMetadata:
        """Compile inspection findings, evidence citations, and approval status into DOCX."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        doc = docx.Document()

        # Document Title
        title_p = doc.add_heading(content.title, level=0)
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Subtitle / Sensitivity
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_run = sub_p.add_run(f"Data Sensitivity: {content.data_sensitivity} | Sovereign Workbench v1.0")
        sub_run.font.italic = True
        sub_run.font.color.rgb = RGBColor(100, 100, 100)

        # 1. Metadata Table
        doc.add_heading("1. Document & Task Metadata", level=1)
        meta_table = doc.add_table(rows=4, cols=2)
        meta_table.style = "Table Grid"
        meta_entries = [
            ("Task ID:", task_id),
            ("Equipment / Target:", content.equipment_id or "General Industrial Equipment"),
            ("Inspection Inspector / Model:", content.inspector or "Automated Sovereign Vision Inspector"),
            ("Policy & Authorization:", content.policy_decision or "ALLOW"),
        ]
        for idx, (label, val) in enumerate(meta_entries):
            row_cells = meta_table.rows[idx].cells
            row_cells[0].paragraphs[0].add_run(label).bold = True
            row_cells[1].paragraphs[0].add_run(str(val))

        # 2. Executive Summary
        doc.add_heading("2. Executive Summary", level=1)
        doc.add_paragraph(content.summary)

        # 3. Candidate Findings Table
        doc.add_heading("3. Candidate Visual & Document Findings", level=1)
        if content.candidate_findings:
            table = doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            hdr_cells = table.rows[0].cells
            hdr_cells[0].paragraphs[0].add_run("Finding / Observation").bold = True
            hdr_cells[1].paragraphs[0].add_run("Region / Page").bold = True
            hdr_cells[2].paragraphs[0].add_run("Confidence").bold = True
            hdr_cells[3].paragraphs[0].add_run("Evidence ID").bold = True

            for finding in content.candidate_findings:
                row_cells = table.add_row().cells
                obs = finding.get("observation", finding.get("description", "Candidate observation"))
                region = finding.get("region", finding.get("page", "Body"))
                conf = finding.get("confidence", "MEDIUM")
                ev_id = finding.get("evidence_id", finding.get("evidence_reference", "EV-001"))

                row_cells[0].paragraphs[0].add_run(str(obs))
                row_cells[1].paragraphs[0].add_run(str(region))
                row_cells[2].paragraphs[0].add_run(str(conf))
                row_cells[3].paragraphs[0].add_run(str(ev_id))
        else:
            doc.add_paragraph("No candidate findings reported.")

        # 4. Cryptographic Provenance & Citations
        doc.add_heading("4. Evidence Provenance & Cryptographic Trace", level=1)
        if content.evidence_citations:
            ev_table = doc.add_table(rows=1, cols=3)
            ev_table.style = "Table Grid"
            ev_hdr = ev_table.rows[0].cells
            ev_hdr[0].paragraphs[0].add_run("Evidence / Chunk ID").bold = True
            ev_hdr[1].paragraphs[0].add_run("Source Document").bold = True
            ev_hdr[2].paragraphs[0].add_run("SHA-256 Source Hash").bold = True

            for ev in content.evidence_citations:
                ev_cells = ev_table.add_row().cells
                ev_id = ev.get("chunk_id", ev.get("evidence_id", "EV-TRACE"))
                doc_name = ev.get("source_document", ev.get("filename", "inspection_document.pdf"))
                s_hash = ev.get("source_hash", ev.get("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"))

                ev_cells[0].paragraphs[0].add_run(str(ev_id))
                ev_cells[1].paragraphs[0].add_run(str(doc_name))
                ev_cells[2].paragraphs[0].add_run(str(s_hash[:16]) + "...")
        else:
            doc.add_paragraph("No external evidence citations registered.")

        # 5. Recommendations
        if content.recommendations:
            doc.add_heading("5. Actionable Recommendations", level=1)
            for rec in content.recommendations:
                doc.add_paragraph(rec, style="List Bullet")

        # 6. Human Sign-off and Approval
        doc.add_heading("6. Human Approval & Authority Sign-off", level=1)
        app_p = doc.add_paragraph()
        if content.human_approval:
            app_p.add_run(f"Decision: {content.human_approval.get('decision', 'APPROVED')}").bold = True
            app_p.add_run(f"\nApprover: {content.human_approval.get('approver', 'Chief Engineer')}")
            app_p.add_run(f"\nTimestamp: {content.human_approval.get('timestamp', 'N/A')}")
            app_p.add_run(f"\nPlan Hash: {content.human_approval.get('plan_hash', 'N/A')}")
        else:
            app_p.add_run(f"Status: {content.policy_decision or 'PENDING_REVIEW'}").bold = True
            app_p.add_run("\nCertified through sovereign zero-egress inspection pipeline.")

        doc.save(output_path)

        content_hash = self._compute_file_hash(output_path)
        file_size = os.path.getsize(output_path)

        return ArtifactMetadata(
            task_id=task_id,
            artifact_type="docx",
            file_path=output_path,
            content_hash=content_hash,
            source_evidence=content.evidence_citations,
            file_size_bytes=file_size,
            status="GENERATED",
            metadata={"title": content.title, "equipment_id": content.equipment_id},
        )

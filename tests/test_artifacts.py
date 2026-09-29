"""Unit and integrity tests for local artifact generation and deterministic verification."""

import os
import pytest
from backend.app.artifacts import (
    ArtifactFactory,
    get_artifact_factory,
    ApprovalNoteContent,
    SpreadsheetContent,
    SpreadsheetSheetData,
    ArtifactVerifier,
    generate_docx_tool,
    generate_xlsx_tool,
)
from tests.fixtures.phase_9_fixtures import (
    SAMPLE_FINDINGS,
    SAMPLE_EVIDENCE_CITATIONS,
)


def test_docx_approval_note_generation_and_reopen(tmp_path):
    """Verify DOCX approval note is generated locally, hashed, and successfully reopened."""
    factory = ArtifactFactory(output_dir=str(tmp_path))
    content = ApprovalNoteContent(
        title="Turbine Flange Inspection Note",
        equipment_id="TURBINE-FLG-01",
        inspector="Senior NDT Inspector",
        summary="Detailed visual inspection identified candidate surface pitting.",
        candidate_findings=SAMPLE_FINDINGS,
        evidence_citations=SAMPLE_EVIDENCE_CITATIONS,
        policy_decision="ALLOW",
        human_approval={
            "decision": "APPROVED",
            "approver": "Chief Engineer Patel",
            "timestamp": "2026-09-29T10:00:00Z",
            "plan_hash": "abc123hash",
        },
        recommendations=["Ultrasonic thickness testing required within 14 days"],
    )

    meta = factory.create_approval_note(content, task_id="task_docx_test")

    assert meta.status == "VERIFIED"
    assert meta.artifact_type == "docx"
    assert os.path.exists(meta.file_path)
    assert meta.file_size_bytes > 0
    assert len(meta.content_hash) == 64  # SHA-256

    # Verify directly with ArtifactVerifier
    v_res = ArtifactVerifier.verify(meta)
    assert v_res.is_verified is True
    assert v_res.checks["docx_reopened_ok"] is True
    assert v_res.checks["hash_matches"] is True
    assert v_res.checks["evidence_citations_valid"] is True


def test_xlsx_workbook_generation_and_reopen(tmp_path):
    """Verify XLSX workbook is generated with multiple sheets, formulas, and can be reopened."""
    factory = ArtifactFactory(output_dir=str(tmp_path))
    content = SpreadsheetContent(
        title="Industrial Sensor Log",
        sheets=[
            SpreadsheetSheetData(
                title="Vibration Measurements",
                headers=["Timestamp", "Vibration mm/s", "Temp C"],
                rows=[
                    ["2026-09-01T08:00", 2.1, 65.4],
                    ["2026-09-01T12:00", 2.3, 67.1],
                    ["2026-09-01T16:00", 4.8, 78.5],
                ],
                include_summary_row=True,
            )
        ],
        provenance={"Source": "Sensor Unit A", "Calibration": "Valid"},
        task_id="task_xlsx_test",
    )

    meta = factory.create_spreadsheet(content)

    assert meta.status == "VERIFIED"
    assert meta.artifact_type == "xlsx"
    assert os.path.exists(meta.file_path)

    v_res = ArtifactVerifier.verify(meta)
    assert v_res.is_verified is True
    assert v_res.checks["xlsx_reopened_ok"] is True
    assert v_res.details["sheet_count"] == 2  # Data sheet + Provenance sheet


def test_artifact_verifier_detects_corrupt_hash(tmp_path):
    """Verify ArtifactVerifier fails if file content has been altered after hashing."""
    factory = ArtifactFactory(output_dir=str(tmp_path))
    meta = factory.create_approval_note(
        ApprovalNoteContent(summary="Baseline note"),
        task_id="task_tamper",
    )

    # Corrupt the content_hash metadata
    tampered_meta = meta.model_copy()
    tampered_meta.content_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    v_res = ArtifactVerifier.verify(tampered_meta)
    assert v_res.is_verified is False
    assert v_res.checks["hash_matches"] is False


def test_artifact_verifier_detects_fabricated_citations(tmp_path):
    """Verify ArtifactVerifier rejects artifacts containing empty or unknown evidence hashes."""
    factory = ArtifactFactory(output_dir=str(tmp_path))
    bad_citations = [
        {"chunk_id": "", "source_document": "Fake.pdf"}
    ]
    meta = factory.create_approval_note(
        ApprovalNoteContent(
            summary="Bad citations note",
            evidence_citations=bad_citations,
        ),
        task_id="task_fake_cit",
    )

    v_res = ArtifactVerifier.verify(meta)
    assert v_res.is_verified is False
    assert v_res.checks["evidence_citations_valid"] is False


def test_tools_generate_docx_and_xlsx(tmp_path):
    """Verify create_docx and create_xlsx tool wrappers."""
    d_out = generate_docx_tool(
        title="Tool Inspection Note",
        summary="Summary via tool invocation",
        task_id="t_tool_d",
    )
    assert d_out["artifact_type"] == "docx"
    assert d_out["status"] in ("GENERATED", "VERIFIED")

    x_out = generate_xlsx_tool(
        title="Tool Spreadsheet",
        sheets=[{"title": "Log", "headers": ["A", "B"], "rows": [[1, 2]]}],
        task_id="t_tool_x",
    )
    assert x_out["artifact_type"] == "xlsx"
    assert x_out["status"] in ("GENERATED", "VERIFIED")

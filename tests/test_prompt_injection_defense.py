"""Test J: Prompt Injection Defense."""

import pytest
from backend.app.multimodal.schemas import DocumentInput
from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
from backend.app.multimodal.prompt_defense import PromptInjectionDefense
from tests.fixtures.multimodal_fixtures import create_prompt_injection_pdf


def test_document_prompt_injection_treated_as_data(tmp_path):
    pdf_path = str(tmp_path / "malicious.pdf")
    create_prompt_injection_pdf(pdf_path)

    doc_input = DocumentInput.from_file(pdf_path)
    pipeline = MultimodalDocumentPipeline()

    result = pipeline.process(doc_input, enable_vlm=False)

    # 1. Pipeline should produce warnings regarding prompt injection attempt
    assert len(result.warnings) > 0
    assert any("Prompt injection" in w for w in result.warnings)

    # 2. Text should be isolated as DATA inside quarantine tags
    text_evidences = [e for e in result.evidence if "DOCUMENT_DATA_QUARANTINE" in (e.text or "")]
    assert len(text_evidences) > 0

    # 3. Verify that raw text still exists as untrusted data, but flagged
    flagged_ev = text_evidences[0]
    assert flagged_ev.metadata.get("injection_flagged") is True
    assert len(flagged_ev.metadata.get("detected_patterns", [])) > 0

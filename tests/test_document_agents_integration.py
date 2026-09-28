"""Test N: Document Agent and Vision Agent Integration."""

import pytest
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.planner import PlanStep
from backend.app.multimodal.schemas import DocumentInput
from tests.fixtures.multimodal_fixtures import create_text_pdf, create_image_file


def test_document_and_vision_agents_resolved_and_execute(tmp_path):
    agent_reg = AgentRegistry()
    tool_reg = ToolRegistry(include_multimodal=True)

    # 1. Verify agents exist in registry
    assert agent_reg.exists("document_agent")
    assert agent_reg.exists("vision_agent")

    doc_agent = agent_reg.get("document_agent")
    vision_agent = agent_reg.get("vision_agent")

    assert "pdf_ingestion" in doc_agent.capabilities
    assert "visual_reasoning" in vision_agent.capabilities

    # 2. Execute document_agent step with real test PDF
    pdf_path = str(tmp_path / "spec.pdf")
    create_text_pdf(pdf_path, "Turbine Pressure: 12.4 MPa")

    executor = AgentExecutor(agent_reg, tool_reg)

    doc_step = PlanStep(
        step_id="step_doc_1",
        agent_id="document_agent",
        capability="pdf_ingestion",
        description="Ingest and parse the turbine technical specification",
        required_tools=["document_type_detect", "pdf_text_extract"],
        expected_output="Normalized document evidence",
    )

    doc_result = executor.execute(
        agent_id="document_agent",
        step=doc_step,
        task_context={"document_path": pdf_path},
    )

    assert doc_result.status == "SUCCESS"
    assert "document_analysis" in doc_result.output
    analysis = doc_result.output["document_analysis"]
    assert analysis["page_count"] >= 1
    assert len(analysis["evidence"]) > 0

    # 3. Execute vision_agent step with image
    img_path = str(tmp_path / "diagram.png")
    create_image_file(img_path, "SENSOR DIAGRAM")

    vision_step = PlanStep(
        step_id="step_vis_1",
        agent_id="vision_agent",
        capability="visual_reasoning",
        description="Analyze sensor diagram",
        required_tools=["vlm_analyze_document"],
        expected_output="Visual observations",
    )

    vis_result = executor.execute(
        agent_id="vision_agent",
        step=vision_step,
        task_context={"file_path": img_path},
    )

    assert vis_result.status == "SUCCESS"
    assert "document_analysis" in vis_result.output

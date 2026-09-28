"""Test A: Deterministic Risk Assessment Layer."""

import pytest
from backend.app.tools.registry import ToolRegistry
from backend.app.orchestration.planner import PlanStep
from backend.app.security.risk import RiskEngine, RiskLevel, RiskFactor, RiskAssessment
from backend.app.security.data_sensitivity import DataSensitivity


def test_risk_levels_classification():
    """Verify LOW, MEDIUM, HIGH, CRITICAL risk classification."""
    engine = RiskEngine()

    # 1. LOW Risk Plan
    low_step = PlanStep(
        step_id="s1",
        description="Read documentation",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_read"],
    )
    low_assessment = engine.assess_plan("task-low", "plan-1", [low_step], DataSensitivity.PUBLIC)
    assert low_assessment.risk_level == RiskLevel.LOW
    assert low_assessment.risk_score <= 0.25

    # 2. MEDIUM Risk Plan
    med_step = PlanStep(
        step_id="s2",
        description="Write output summary",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["file_write"],
    )
    med_assessment = engine.assess_plan("task-med", "plan-2", [med_step], DataSensitivity.INTERNAL)
    assert med_assessment.risk_level == RiskLevel.MEDIUM
    assert 0.25 < med_assessment.risk_score <= 0.60
    assert RiskFactor.FILE_WRITE.value in med_assessment.risk_factors

    # 3. HIGH Risk Plan (e.g. sandbox code execution)
    high_step = PlanStep(
        step_id="s3",
        description="Execute python script in sandbox",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    high_assessment = engine.assess_plan("task-high", "plan-3", [high_step], DataSensitivity.INTERNAL)
    assert high_assessment.risk_level == RiskLevel.HIGH
    assert RiskFactor.CODE_EXECUTION.value in high_assessment.risk_factors

    # 4. CRITICAL Risk Plan (e.g. sensitive data + code execution, or external network)
    crit_step = PlanStep(
        step_id="s4",
        description="Send telemetry to external network endpoint",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=[],
    )
    crit_assessment = engine.assess_plan("task-crit", "plan-4", [crit_step], DataSensitivity.RESTRICTED)
    assert crit_assessment.risk_level == RiskLevel.CRITICAL
    assert RiskFactor.EXTERNAL_NETWORK_ACCESS.value in crit_assessment.risk_factors
    assert RiskFactor.SENSITIVE_DATA_ACCESS.value in crit_assessment.risk_factors


def test_major_risk_factors_detection():
    """Verify each major risk factor is identified."""
    engine = RiskEngine()

    # file_delete factor
    del_step = PlanStep(
        step_id="s_del",
        description="Delete temporary files from disk",
        capability="reasoning",
        agent_id="reasoning_agent",
        required_tools=["file_write"],
    )
    ass_del = engine.assess_plan("t1", "p1", [del_step])
    assert RiskFactor.FILE_DELETE.value in ass_del.risk_factors

    # spreadsheet modification
    calc_step = PlanStep(
        step_id="s_calc",
        description="Update spreadsheet financial rows",
        capability="data_processing",
        agent_id="data_agent",
        required_tools=["create_xlsx"],
    )
    ass_calc = engine.assess_plan("t2", "p2", [calc_step])
    assert RiskFactor.SPREADSHEET_MODIFICATION.value in ass_calc.risk_factors

    # document generation
    doc_step = PlanStep(
        step_id="s_doc",
        description="Generate official briefing note",
        capability="document_extraction",
        agent_id="document_agent",
        required_tools=["create_docx"],
    )
    ass_doc = engine.assess_plan("t3", "p3", [doc_step])
    assert RiskFactor.DOCUMENT_GENERATION.value in ass_doc.risk_factors

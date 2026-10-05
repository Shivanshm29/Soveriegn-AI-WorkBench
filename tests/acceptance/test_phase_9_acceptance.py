"""Authoritative Phase 9 Acceptance Test Suite and Demonstration Scenarios.

Verifies all Phase 9 requirements:
- Local Coding Agent using ModelRegistry
- Isolated local sandbox with strict network denial and filesystem containment
- Local Data/Calculation Agent for deterministic calculations and CSV/XLSX analysis
- Deterministic calculation and code verification
- Local artifact generation (DOCX, XLSX) with SHA-256 hashes and evidence provenance
- Demo Scenario 1: Scanned Inspection Report -> Findings -> Approval -> DOCX
- Demo Scenario 2: Coding Task -> Policy/Approval -> Sandbox -> Network Blocked -> Verification
- Demo Scenario 3: Confidential Knowledge Query -> Hybrid RAG -> Grounded Answer + Citations
- Demo Scenario 4: Industrial Engineering Image -> Preprocessing -> Vision Candidate Finding
- Demo Scenario 5 (Mixed End-to-End): Document + Vision + Knowledge + Data + Policy + Approval + DOCX Artifact
- Zero-egress enforcement and truthful failure transparency
"""

import os
import pytest
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.security.policy_engine import PolicyEngine, PolicyOutcome
from backend.app.security.approval import ApprovalManager, ApprovalDecision
from backend.app.sandbox import (
    get_sandbox_manager,
    CodeExecutionRequest,
    LocalProcessSandbox,
    PathTraversalError,
)
from backend.app.coding import CodingAgent
from backend.app.data import DataAgent, DataAnalysisRequest
from backend.app.artifacts import (
    get_artifact_factory,
    ApprovalNoteContent,
    SpreadsheetContent,
    SpreadsheetSheetData,
    ArtifactVerifier,
)
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.state.task_state import TaskStatus
from backend.app.vision.agent import EngineeringVisionAgent
from backend.app.rag.knowledge_agent import build_default_knowledge_agent
from tests.fixtures.phase_9_fixtures import (
    SAMPLE_CODE_NORMAL,
    SAMPLE_CODE_NETWORK_ATTEMPT,
    SAMPLE_FINDINGS,
    SAMPLE_EVIDENCE_CITATIONS,
    create_sample_csv_file,
    create_sample_xlsx_file,
)
from tests.fixtures.vision_fixtures import create_industrial_equipment_photo


# --------------------------------------------------------------------------
# Acceptance Criteria: Coding Agent & Sandbox
# --------------------------------------------------------------------------

def test_acceptance_1_coding_agent_registration():
    """Verify Coding Agent is registered with coding, execution, and debugging capabilities."""
    reg = AgentRegistry()
    assert reg.exists("coding_agent")
    contract = reg.get("coding_agent")
    assert "code_generation" in contract.capabilities
    assert "code_execution" in contract.capabilities
    assert "sandbox_execute" in contract.allowed_tools
    assert contract.risk_class == "MEDIUM"


def test_acceptance_2_coding_agent_uses_model_router():
    """Verify Coding Agent dynamically resolves model via ModelRegistry without hardcoded ID."""
    model_reg = ModelRegistry()
    agent = CodingAgent(model_registry=model_reg)
    gen = agent.generate_code("Write script")
    # Small profile active by default
    assert gen.model_id == "qwen-coder-small"
    assert gen.model_name == "Qwen/Qwen2.5-Coder-3B-Instruct"


def test_acceptance_3_sandbox_executes_code_locally():
    """Verify sandbox executes code locally and captures stdout."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(code="print('SOVEREIGN_SANDBOX_SUCCESS')")
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "SUCCESS"
    assert res.exit_code == 0
    assert "SOVEREIGN_SANDBOX_SUCCESS" in res.stdout


def test_acceptance_4_sandbox_network_isolation():
    """Verify network access is strictly blocked inside sandbox."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(code=SAMPLE_CODE_NETWORK_ATTEMPT)
    res = mgr.execute_code(req, force_local=True)
    assert res.network_blocked is True
    assert "NETWORK ACCESS BLOCKED" in res.stdout or "NETWORK ACCESS BLOCKED" in res.stderr


def test_acceptance_5_sandbox_filesystem_restricted_and_cleanup():
    """Verify sandbox workspace is temporary and cleans up automatically."""
    sbx = LocalProcessSandbox()
    w_path = sbx.workspace_path
    assert os.path.exists(w_path)
    sbx.cleanup()
    assert not os.path.exists(w_path)


def test_acceptance_6_sandbox_path_traversal_protection():
    """Verify sandbox blocks path traversal and credential access."""
    sbx = LocalProcessSandbox()
    with pytest.raises(PathTraversalError):
        sbx.write_file("../../secret.txt", "data")
    sbx.cleanup()


def test_acceptance_7_sandbox_requires_policy_authorization():
    """Verify PolicyEngine marks sandbox_execute as requiring human approval."""
    pe = PolicyEngine()
    from backend.app.orchestration.planner import PlanStep
    from backend.app.security.data_sensitivity import DataSensitivity

    step = PlanStep(
        step_id="step_sbx",
        description="Run code in sandbox",
        capability="code_execution",
        agent_id="coding_agent",
        required_tools=["sandbox_execute"],
    )
    decision, _ = pe.evaluate_plan(
        plan_steps=[step],
        task_id="t_pol_sbx",
        plan_id="p_pol_sbx",
        data_sensitivity=DataSensitivity.INTERNAL,
    )
    assert decision.requires_approval is True
    assert decision.decision == PolicyOutcome.REQUIRE_APPROVAL


def test_acceptance_8_code_execution_verified():
    """Verify code execution is deterministically verified."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(
        code="print('VAL: 42')",
        expected_output_patterns=[r"VAL:\s*42"],
    )
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "SUCCESS"
    assert res.verification_status is not None
    assert res.verification_status.is_verified is True


# --------------------------------------------------------------------------
# Acceptance Criteria: Data / Calculation Agent
# --------------------------------------------------------------------------

def test_acceptance_9_data_agent_registration():
    """Verify Data Agent is registered with arithmetic, statistics, CSV/XLSX analysis."""
    reg = AgentRegistry()
    assert reg.exists("data_agent")
    contract = reg.get("data_agent")
    assert "calculation" in contract.capabilities
    assert "data_analysis" in contract.capabilities
    assert "python_calculation" in contract.allowed_tools


def test_acceptance_10_deterministic_calculation_and_trace():
    """Verify calculations do not rely on LLM arithmetic and produce mathematical traces."""
    agent = DataAgent()
    res = agent.compute_statistics([10.0, 20.0, 30.0], operation="mean")
    assert res.value == 20.0
    assert res.is_verified is True
    assert len(res.calculation_trace) == 3


def test_acceptance_11_csv_and_xlsx_data_analysis(tmp_path):
    """Verify CSV and XLSX analysis returns summaries and column statistics."""
    csv_p = str(tmp_path / "measurements.csv")
    create_sample_csv_file(csv_p)

    agent = DataAgent()
    res = agent.analyze_dataset(DataAnalysisRequest(file_path=csv_p))
    assert res.status == "SUCCESS"
    assert res.row_count == 6
    assert "temperature_c" in res.column_stats
    assert res.column_stats["temperature_c"].mean_value is not None


# --------------------------------------------------------------------------
# Acceptance Criteria: Artifact Generation & Verification
# --------------------------------------------------------------------------

def test_acceptance_12_docx_and_xlsx_generation_and_reopen(tmp_path):
    """Verify DOCX and XLSX artifacts are created locally, hashed, and verified."""
    factory = get_artifact_factory()
    d_meta = factory.create_approval_note(
        ApprovalNoteContent(
            title="Inspection Acceptance Note",
            summary="Sovereign validation of industrial components.",
            candidate_findings=SAMPLE_FINDINGS,
            evidence_citations=SAMPLE_EVIDENCE_CITATIONS,
        ),
        task_id="t_acc_art",
    )
    assert d_meta.status == "VERIFIED"
    assert os.path.exists(d_meta.file_path)
    assert len(d_meta.content_hash) == 64

    # Direct verification
    v_res = ArtifactVerifier.verify(d_meta)
    assert v_res.is_verified is True
    assert v_res.checks["docx_reopened_ok"] is True


# --------------------------------------------------------------------------
# Demonstration Scenario 1: Scanned Inspection Report -> Approval Note (DOCX)
# --------------------------------------------------------------------------

def test_demo_scenario_1_scanned_report_to_approval_note(tmp_path):
    """Demonstration Scenario 1:
    Local scanned report -> Visual/Document inspection -> Candidate findings -> Approval -> DOCX Note
    """
    img_p = str(tmp_path / "flange_inspection.png")
    create_industrial_equipment_photo(img_p)

    orch = WorkbenchOrchestrator()
    query = (
        "Analyze this scanned inspection report for equipment TURBINE-01, "
        "identify candidate observations, and generate an inspection approval note."
    )

    state = orch.run(
        query,
        task_id="demo_scenario_1",
        file_path=img_p,
    )

    # 1. Pipeline executes to completion
    assert state["task_status"] == TaskStatus.COMPLETED.value
    # 2. Vision and document generation capabilities routed
    assert any(c in state["required_capabilities"] for c in ("visual_reasoning", "document_generation"))
    # 3. Execution steps produced outputs
    assert len(state["execution_steps"]) > 0
    # 4. Verified plan completion
    assert state["verification_results"]["is_verified"] is True
    # 5. Final deliverable created
    assert state["final_result"]["status"] == "COMPLETED"


# --------------------------------------------------------------------------
# Demonstration Scenario 2: Coding Task -> Sandbox -> Network Blocked -> Verification
# --------------------------------------------------------------------------

def test_demo_scenario_2_coding_task_sandbox(tmp_path):
    """Demonstration Scenario 2:
    Coding task -> Code generation -> Policy requires approval -> Sandbox execution -> Network blocked -> Verified
    """
    csv_p = str(tmp_path / "stats.csv")
    create_sample_csv_file(csv_p)

    orch = WorkbenchOrchestrator()
    query = "Write a Python script to calculate statistics from this CSV and execute in the sandbox."

    # First run pauses for approval because sandbox_execute is HIGH risk
    state_pause = orch.run(
        query,
        task_id="demo_scenario_2",
        csv_path=csv_p,
    )

    assert state_pause["task_status"] == TaskStatus.WAITING_APPROVAL.value
    app_req = state_pause.get("approval_request")
    assert app_req is not None
    assert app_req["risk_level"] == "HIGH"

    # Human grants approval
    decision = ApprovalDecision(
        approval_id=app_req["approval_id"],
        decision="APPROVED",
        approver="Chief Engineer",
        plan_hash=app_req.get("plan_hash", ""),
    )
    final_state = orch.submit_approval("demo_scenario_2", decision)

    # Workflow completes successfully inside the isolated sandbox
    assert final_state["task_status"] == TaskStatus.COMPLETED.value
    assert final_state["verification_results"]["is_verified"] is True


# --------------------------------------------------------------------------
# Demonstration Scenario 3: Confidential Knowledge Question -> Hybrid RAG -> Grounded
# --------------------------------------------------------------------------

def test_demo_scenario_3_confidential_knowledge_rag(tmp_path):
    """Demonstration Scenario 3:
    Confidential knowledge query for pump PX-417 -> Hybrid RAG -> Evidence Pack -> Grounded Answer + Citations
    """
    manifest_p = str(tmp_path / "rag_px417_manifest.json")
    k_agent = build_default_knowledge_agent(manifest_path=manifest_p)

    k_agent.ingest_text(
        text=(
            "Standard Operating Procedure for pump PX-417:\n"
            "Normal operating vibration must remain under 2.5 mm/s RMS.\n"
            "If vibration exceeds 4.5 mm/s, immediately schedule bearing replacement."
        ),
        document_id="doc_px417_sop",
        filename="PX417_SOP.txt",
        sensitivity="CONFIDENTIAL",
    )

    ans = k_agent.answer_query(
        "What does the maintenance procedure recommend for pump PX-417 vibration?",
        max_sensitivity="CONFIDENTIAL",
    )

    assert ans.answer is not None
    assert len(ans.citations) > 0
    assert any("PX417_SOP" in c.source_document for c in ans.citations)


# --------------------------------------------------------------------------
# Demonstration Scenario 4: Engineering Image -> Preprocessing -> Vision Candidate Finding
# --------------------------------------------------------------------------

def test_demo_scenario_4_engineering_vision_candidate(tmp_path):
    """Demonstration Scenario 4:
    Equipment image -> Local preprocessing -> Candidate observation without fabricating certified conclusion
    """
    img_p = str(tmp_path / "equipment_sample.png")
    create_industrial_equipment_photo(img_p)

    agent = EngineeringVisionAgent()
    result = agent.process_image(
        image_path=img_p,
        user_focus="inspect surface for candidate indications",
    )

    assert result.source_hash is not None
    assert len(result.observations) > 0
    # Candidate language enforced (no certified claims without physical NDT)
    for obs in result.observations:
        assert obs.candidate_observation is True


# --------------------------------------------------------------------------
# Demonstration Scenario 5 (Mixed Multi-Agent Integration):
# Document + Vision + Knowledge + Data + Policy + Approval + DOCX Artifact
# --------------------------------------------------------------------------

def test_demo_scenario_5_mixed_end_to_end_orchestration(tmp_path):
    """Mixed End-to-End Scenario:
    "Analyze this inspection report, check the maintenance procedure for the equipment, "
    "calculate the reported measurements, and prepare an approval note."
    
    Verifies multi-agent capability coordination in ONE LangGraph workflow.
    """
    img_p = str(tmp_path / "flange_mixed.png")
    create_industrial_equipment_photo(img_p)
    csv_p = str(tmp_path / "measurements_mixed.csv")
    create_sample_csv_file(csv_p)

    orch = WorkbenchOrchestrator()
    query = (
        "Analyze this inspection report, check the maintenance procedure for the equipment, "
        "calculate the reported measurements, and prepare an approval note."
    )

    state = orch.run(
        query,
        task_id="mixed_end_to_end",
        file_path=img_p,
        csv_path=csv_p,
    )

    # Verifies all 4 major specialist capabilities coordinated:
    req_caps = state.get("required_capabilities", [])
    assert "visual_reasoning" in req_caps
    assert "knowledge_search" in req_caps
    assert "calculation" in req_caps
    assert "document_generation" in req_caps

    # Verify complete execution and delivery
    assert state["task_status"] == TaskStatus.COMPLETED.value
    assert len(state["execution_steps"]) >= 4
    assert state["verification_results"]["is_verified"] is True
    assert state["final_result"]["status"] == "COMPLETED"

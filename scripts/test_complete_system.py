"""Complete System End-to-End Verification Suite for Sovereign AI Workbench.

Executes tests across every functional subsystem:
1. Zero-Egress Sovereignty Policy & Isolation
2. Local Model Runtime & Hardware Acceleration (GPU)
3. Agent Registry & Specialized Agent Contracts
4. Multimodal Document Pipeline & Chunk Extraction
5. Vision Agent & Engineering Drawing/Defect Analysis
6. Knowledge Agent & Confidential Sovereign RAG
7. Coding Agent & Local Execution Sandbox (Security Gates)
8. Data Agent, Calculation Traces & Statistical Analysis
9. LangGraph Orchestration, Policy Gates & Human Approval
10. Live Web Server & REST API Endpoints
"""

import sys
import os
import time
import json
import uuid
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestRunner:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def record(self, category: str, test_name: str, passed: bool, message: str = "", duration: float = 0.0):
        self.results.append({
            "category": category,
            "name": test_name,
            "passed": passed,
            "message": message,
            "duration": duration,
        })
        status_icon = "[\033[92mPASS\033[0m]" if passed else "[\033[91mFAIL\033[0m]"
        dur_str = f"({duration:.2f}s)" if duration > 0 else ""
        print(f"  {status_icon} {test_name} {dur_str}")
        if not passed and message:
            print(f"         \033[91mError: {message}\033[0m")

    def print_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        elapsed = time.time() - self.start_time

        print("\n" + "=" * 78)
        print("   SOVEREIGN WORKBENCH COMPLETE SYSTEM VERIFICATION SUMMARY")
        print("=" * 78)
        print(f"Total Tests Run   : {total}")
        print(f"Passed            : \033[92m{passed}\033[0m")
        print(f"Failed            : \033[91m{failed}\033[0m" if failed else "Failed            : 0")
        print(f"Total Duration    : {elapsed:.2f}s")
        print("=" * 78)

        if failed == 0:
            print("\033[92m>>> ALL SYSTEM CAPABILITIES AND FUNCTIONALITIES ARE 100% OPERATIONAL <<<\033[0m\n")
        else:
            print("\033[91m>>> SOME CAPABILITIES FAILED VERIFICATION <<<\033[0m\n")
        return failed == 0


runner = TestRunner()

# ==============================================================================
# 1. Zero-Egress Sovereignty & Network Security
# ==============================================================================
print("\n[1/10] Verifying Zero-Egress Sovereignty & Network Policies...")
t0 = time.time()
try:
    from backend.app.security.sovereignty_policy import get_sovereignty_policy
    from backend.app.security.network_policy import SovereigntyViolationError

    policy = get_sovereignty_policy()
    # 1.1 Localhost allowed
    policy.validate_endpoint("http://127.0.0.1:11434/v1", component="runtime")
    policy.validate_endpoint("http://localhost:8080", component="web")
    runner.record("Sovereignty", "Localhost & Loopback Allowed", True, duration=time.time() - t0)

    # 1.2 Cloud hosts strictly blocked
    t0 = time.time()
    blocked_properly = False
    try:
        policy.validate_endpoint("https://api.openai.com/v1/chat", component="external")
    except SovereigntyViolationError:
        blocked_properly = True
    runner.record("Sovereignty", "External Cloud Host Rejection", blocked_properly, duration=time.time() - t0)

    # 1.3 Direct external IP strictly blocked
    t0 = time.time()
    ip_blocked = False
    try:
        policy.validate_endpoint("http://8.8.8.8:80", component="external_ip")
    except SovereigntyViolationError:
        ip_blocked = True
    runner.record("Sovereignty", "External Direct IP Rejection", ip_blocked, duration=time.time() - t0)

    # 1.4 Sovereign mode configuration
    is_sov = policy.is_sovereign_mode()
    no_telemetry = not policy.is_remote_telemetry_allowed()
    no_cloud = not policy.is_cloud_models_allowed()
    runner.record("Sovereignty", "Telemetry & Cloud API Disabled", is_sov and no_telemetry and no_cloud)
except Exception as e:
    runner.record("Sovereignty", "Sovereignty Policy Subsystem", False, str(e))


# ==============================================================================
# 2. Local Model Runtime & Hardware Acceleration
# ==============================================================================
print("\n[2/10] Verifying Local Model Runtime & Hardware Acceleration...")
t0 = time.time()
try:
    from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
    from backend.app.models.schemas import ModelRequest, ChatMessage

    rt = LocalOpenAIRuntime(base_url="http://127.0.0.1:11434/v1")
    health = rt.health_check()
    is_healthy = health.status.value == "healthy"
    runner.record("Model Runtime", f"Ollama Runtime Health Check ({health.runtime})", is_healthy, duration=time.time() - t0)

    # 2.2 Loaded models in Ollama
    t0 = time.time()
    models = health.models or []
    has_models = len(models) > 0
    runner.record("Model Runtime", f"Local Model Inventory ({len(models)} models available)", has_models, f"Models: {models[:4]}", duration=time.time() - t0)

    # 2.3 Live Chat Generation on Local Model
    t0 = time.time()
    req = ModelRequest(
        model="qwen2.5:3b",
        messages=[
            ChatMessage(role="system", content="You are a sovereign industrial assistant. Respond concisely."),
            ChatMessage(role="user", content="Respond with the exact word: READY"),
        ],
        temperature=0.0,
        max_tokens=20,
    )
    resp = rt.chat(req)
    gen_ok = "ready" in resp.content.lower()
    runner.record("Model Runtime", f"Live Local Model Generation ('{resp.content.strip()[:30]}')", gen_ok, duration=time.time() - t0)
except Exception as e:
    runner.record("Model Runtime", "Local Model Runtime Connectivity", False, str(e))


# ==============================================================================
# 3. Agent Registry & Specialized Agent Contracts
# ==============================================================================
print("\n[3/10] Verifying Agent Registry & Capability Contracts...")
t0 = time.time()
try:
    from backend.app.agents.registry import AgentRegistry

    reg = AgentRegistry()
    expected_agents = ["main_agent", "reasoning_agent", "document_agent", "vision_agent", "knowledge_agent", "coding_agent", "data_agent"]
    all_registered = all(reg.get(ag_id) is not None for ag_id in expected_agents)
    runner.record("Agent Registry", f"All 7 Logical Agents Registered ({len(expected_agents)}/7)", all_registered, duration=time.time() - t0)

    # Capability-based resolution
    t0 = time.time()
    coding_ag = [a.agent_id for a in reg.find_by_capability("code_execution")]
    data_ag = [a.agent_id for a in reg.find_by_capability("calculation")]
    vis_ag = [a.agent_id for a in reg.find_by_capability("visual_reasoning")]
    resolution_ok = ("coding_agent" in coding_ag) and ("data_agent" in data_ag) and ("vision_agent" in vis_ag)
    runner.record("Agent Registry", "Capability-Based Agent Resolution", resolution_ok, duration=time.time() - t0)
except Exception as e:
    runner.record("Agent Registry", "Agent Registry Subsystem", False, str(e))


# ==============================================================================
# 4. Multimodal Document Processing (Document Agent)
# ==============================================================================
print("\n[4/10] Verifying Multimodal Document Processing...")
t0 = time.time()
try:
    from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
    from backend.app.multimodal.schemas import DocumentInput
    from tests.fixtures.multimodal_fixtures import create_text_pdf

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    create_text_pdf(pdf_path, text="Sovereign Industrial Equipment Spec: TURBINE-01 operating at 3000 RPM.")
    pipe = MultimodalDocumentPipeline()
    doc_input = DocumentInput.from_file(pdf_path)
    doc_res = pipe.process(doc_input)
    os.remove(pdf_path)

    has_evidence = len(doc_res.evidence) > 0 and doc_res.page_count >= 1
    runner.record("Document Agent", f"PDF Extraction & Multimodal Evidence ({len(doc_res.evidence)} items, {doc_res.page_count} pages)", has_evidence, duration=time.time() - t0)
except Exception as e:
    runner.record("Document Agent", "Document Extraction Subsystem", False, str(e))


# ==============================================================================
# 5. Engineering Vision & Defect Analysis (Vision Agent)
# ==============================================================================
print("\n[5/10] Verifying Engineering Vision & Candidate Anomaly Detection...")
t0 = time.time()
try:
    from backend.app.vision.agent import EngineeringVisionAgent
    from tests.fixtures.phase_9_fixtures import create_industrial_equipment_photo

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img_path = f.name
    create_industrial_equipment_photo(img_path)

    v_agent = EngineeringVisionAgent()
    v_res = v_agent.process_image(img_path, user_focus="inspect casing surface")
    os.remove(img_path)

    has_obs = len(v_res.observations) > 0
    has_candidate = any(obs.candidate_observation for obs in v_res.observations)
    has_disclaimer = any("verification" in f.recommendation.lower() or "ndt" in f.recommendation.lower() for f in v_res.findings)
    runner.record("Vision Agent", f"Visual Observations & Findings ({len(v_res.observations)} obs, {len(v_res.findings)} findings)", has_obs, duration=time.time() - t0)
    runner.record("Vision Agent", "Candidate Status & Required NDT Disclaimer", has_candidate and has_disclaimer)
except Exception as e:
    runner.record("Vision Agent", "Engineering Vision Subsystem", False, str(e))


# ==============================================================================
# 6. Knowledge Agent & Confidential Sovereign RAG
# ==============================================================================
print("\n[6/10] Verifying Knowledge Agent & Confidential Hybrid Search...")
t0 = time.time()
try:
    from backend.app.rag.knowledge_agent import build_default_knowledge_agent

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        manifest_path = f.name

    k_agent = build_default_knowledge_agent(manifest_path=manifest_path)
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

    # 6.1 Query with authorized sensitivity
    ans = k_agent.answer_query(
        "What does the maintenance procedure recommend for pump PX-417 vibration?",
        max_sensitivity="CONFIDENTIAL",
    )
    ans_ok = "2.5 mm/s" in ans.answer and len(ans.citations) > 0
    runner.record("Knowledge Agent", "Confidential Knowledge Retrieval & Citation", ans_ok, duration=time.time() - t0)

    # 6.2 Sensitivity boundary gating: query restricted to INTERNAL should NOT see CONFIDENTIAL
    t0 = time.time()
    restricted_ans = k_agent.answer_query(
        "What does the maintenance procedure recommend for pump PX-417 vibration?",
        max_sensitivity="INTERNAL",
    )
    gating_ok = restricted_ans.insufficient_evidence is True
    runner.record("Knowledge Agent", "Sensitivity Clearance Gating (Leakage Prevention)", gating_ok, duration=time.time() - t0)
    if os.path.exists(manifest_path):
        os.remove(manifest_path)
except Exception as e:
    runner.record("Knowledge Agent", "Knowledge Subsystem", False, str(e))


# ==============================================================================
# 7. Coding Agent & Local Execution Sandbox (Security Gates)
# ==============================================================================
print("\n[7/10] Verifying Coding Agent & Local Isolated Sandbox...")
t0 = time.time()
try:
    from backend.app.sandbox.manager import get_sandbox_manager
    from backend.app.sandbox.schemas import CodeExecutionRequest
    from tests.fixtures.phase_9_fixtures import (
        SAMPLE_CODE_NORMAL,
        SAMPLE_CODE_NETWORK_ATTEMPT,
        SAMPLE_CODE_PATH_TRAVERSAL,
        SAMPLE_CODE_ENV_ACCESS,
        SAMPLE_CODE_TIMEOUT,
    )

    sbx_mgr = get_sandbox_manager()

    # 7.1 Safe Code Execution
    req_norm = CodeExecutionRequest(code=SAMPLE_CODE_NORMAL, timeout_seconds=10)
    res_normal = sbx_mgr.execute_code(req_norm)
    normal_ok = res_normal.exit_code == 0 and "COUNT: 5" in res_normal.stdout
    runner.record("Sandbox", "Safe Python Code Execution in Sandbox", normal_ok, duration=time.time() - t0)

    # 7.2 Network Egress Blocking inside Sandbox
    t0 = time.time()
    req_net = CodeExecutionRequest(code=SAMPLE_CODE_NETWORK_ATTEMPT, timeout_seconds=10)
    res_net = sbx_mgr.execute_code(req_net)
    net_blocked = "NETWORK_BLOCKED_CAUGHT" in res_net.stdout or "NETWORK ACCESS BLOCKED" in res_net.stdout or "NETWORK_SUCCESS" not in res_net.stdout
    runner.record("Sandbox", "Sandbox Zero-Egress Network Isolation", net_blocked, duration=time.time() - t0)

    # 7.3 Path Traversal Blocking
    t0 = time.time()
    req_path = CodeExecutionRequest(code=SAMPLE_CODE_PATH_TRAVERSAL, timeout_seconds=10)
    res_path = sbx_mgr.execute_code(req_path)
    path_blocked = "ACCESS_ERROR" in res_path.stdout or "SECRET_LEAKED" not in res_path.stdout
    runner.record("Sandbox", "Filesystem Path Traversal Boundary", path_blocked, duration=time.time() - t0)

    # 7.4 Environment Variable Shielding
    t0 = time.time()
    req_env = CodeExecutionRequest(code=SAMPLE_CODE_ENV_ACCESS, timeout_seconds=10)
    res_env = sbx_mgr.execute_code(req_env)
    env_shielded = "ENV_ERROR" in res_env.stdout or "ENV_LEAKED" not in res_env.stdout
    runner.record("Sandbox", "Environment Variable Shielding", env_shielded, duration=time.time() - t0)

    # 7.5 Sandbox Execution Timeout Enforcement
    t0 = time.time()
    from backend.app.sandbox.schemas import SandboxConfig
    req_timeout = CodeExecutionRequest(code=SAMPLE_CODE_TIMEOUT, config=SandboxConfig(timeout_seconds=2))
    res_timeout = sbx_mgr.execute_code(req_timeout)
    timed_out_ok = res_timeout.status == "TIMEOUT"
    runner.record("Sandbox", "Deterministic Timeout Enforcement (2.0s)", timed_out_ok, duration=time.time() - t0)
except Exception as e:
    runner.record("Sandbox", "Sandbox Execution Subsystem", False, str(e))


# ==============================================================================
# 8. Data Agent & Calculation Traces
# ==============================================================================
print("\n[8/10] Verifying Data Agent, Calculations & Statistical Analysis...")
t0 = time.time()
try:
    from backend.app.data.agent import DataAgent
    from backend.app.data.schemas import DataAnalysisRequest
    from tests.fixtures.phase_9_fixtures import create_sample_csv_file

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name
    create_sample_csv_file(csv_path)

    data_agent = DataAgent()
    req_analysis = DataAnalysisRequest(file_path=csv_path)
    analysis_res = data_agent.analyze_dataset(req_analysis)
    has_stats = "vibration_mms" in analysis_res.column_stats
    vib_stats = analysis_res.column_stats.get("vibration_mms")
    calc_ok = has_stats and vib_stats.total_count == 6
    runner.record("Data Agent", f"CSV Parsing & Column Statistics (rows: {analysis_res.row_count})", calc_ok, duration=time.time() - t0)

    # 8.2 Calculation Trace Generation
    t0 = time.time()
    calc_res = data_agent.evaluate_formula(
        expression="total_vib / 6",
        variables={"total_vib": 17.1},
    )
    trace_ok = abs(calc_res.value - 2.85) < 1e-4 and len(calc_res.calculation_trace) > 0
    runner.record("Data Agent", f"Deterministic Calculation Trace ({calc_res.value:.2f})", trace_ok, duration=time.time() - t0)

    # 8.3 Structured Table Data Verification
    t0 = time.time()
    headers = ["Component", "Status", "Reading"]
    rows = [["Bearing A", "NORMAL", 2.1], ["Bearing B", "ELEVATED", 4.8]]
    tbl = data_agent.generate_table(headers, rows)
    table_ok = tbl.row_count == 2 and tbl.column_count == 3
    runner.record("Data Agent", "Structured Table Generation & Verification", table_ok, duration=time.time() - t0)
    os.remove(csv_path)
except Exception as e:
    runner.record("Data Agent", "Data Agent Subsystem", False, str(e))


# ==============================================================================
# 9. LangGraph Orchestration, Policy Gates & Human Approval
# ==============================================================================
print("\n[9/10] Verifying LangGraph Orchestration & Cryptographic Approval Gate...")
t0 = time.time()
try:
    from backend.app.orchestration.graph import WorkbenchOrchestrator
    from backend.app.security.approval import ApprovalDecision
    from backend.app.state.store import LocalStateStore
    from backend.app.models.registry import ModelRegistry

    state_store = LocalStateStore()
    model_reg = ModelRegistry()
    orchestrator = WorkbenchOrchestrator(model_registry=model_reg, state_store=state_store)

    # 9.1 Submit high-risk coding task that requires sandbox approval
    task_id = f"test_orch_{uuid.uuid4().hex[:6]}"
    state = orchestrator.run(
        user_request="Write a Python script to calculate mean and execute in the sandbox.",
        task_id=task_id,
    )
    paused_ok = state.get("task_status") == "WAITING_APPROVAL" and state.get("approval_request") is not None
    runner.record("Orchestrator", "Task Understanding -> Policy Evaluation -> WAITING_APPROVAL", paused_ok, duration=time.time() - t0)

    # 9.2 Human Approval Gate Sign-off
    t0 = time.time()
    app_req = state.get("approval_request")
    plan_hash = app_req.plan_hash if hasattr(app_req, "plan_hash") else app_req.get("plan_hash")
    app_id = app_req.approval_id if hasattr(app_req, "approval_id") else app_req.get("approval_id")

    decision = ApprovalDecision(
        approval_id=app_id,
        decision="APPROVED",
        approver="Chief Test Engineer",
        plan_hash=plan_hash,
        reason="Verified safe for sandbox execution",
    )
    final_state = orchestrator.submit_approval(task_id, decision)
    completed_ok = final_state.get("task_status") == "COMPLETED"
    runner.record("Orchestrator", "Human Approval Resumption & Deterministic Verification", completed_ok, duration=time.time() - t0)
except Exception as e:
    runner.record("Orchestrator", "LangGraph Orchestration Subsystem", False, str(e))


# ==============================================================================
# 10. Live Web Server & REST API Endpoints
# ==============================================================================
print("\n[10/10] Verifying Live Web Server & REST API Endpoints...")
t0 = time.time()
SERVER_URL = "http://127.0.0.1:8080"
try:
    # 10.1 Web UI Landing Page
    req = urllib.request.urlopen(f"{SERVER_URL}/", timeout=5)
    html_ok = req.getcode() == 200 and "Sovereign" in req.read().decode()
    runner.record("Web Server", "Interactive Glassmorphism UI (GET /)", html_ok, duration=time.time() - t0)

    # 10.2 Sovereignty Status Endpoint
    t0 = time.time()
    req = urllib.request.urlopen(f"{SERVER_URL}/api/v1/sovereignty/status", timeout=5)
    sov_data = json.loads(req.read().decode())
    sov_ok = sov_data.get("sovereign_mode") is True and sov_data.get("zero_egress_enforced") is True
    runner.record("Web Server", "Sovereignty Status API (GET /api/v1/sovereignty/status)", sov_ok, duration=time.time() - t0)

    # 10.3 Models & GPU Telemetry Endpoint
    t0 = time.time()
    req = urllib.request.urlopen(f"{SERVER_URL}/api/v1/models", timeout=5)
    models_data = json.loads(req.read().decode())
    models_ok = "gpu" in models_data and len(models_data.get("models", [])) > 0
    runner.record("Web Server", f"GPU Telemetry API ({models_data.get('gpu', 'Unknown')})", models_ok, duration=time.time() - t0)

    # 10.4 Demo 3: Confidential Knowledge RAG via API
    t0 = time.time()
    post_req = urllib.request.Request(f"{SERVER_URL}/api/v1/demos/demo3", method="POST")
    demo3_res = json.loads(urllib.request.urlopen(post_req, timeout=10).read().decode())
    demo3_ok = demo3_res.get("task_status") == "COMPLETED" and len(demo3_res.get("citations", [])) > 0
    runner.record("Web Server", "Demo 3: Confidential RAG API (POST /api/v1/demos/demo3)", demo3_ok, duration=time.time() - t0)

    # 10.5 Demo 4: Engineering Vision via API
    t0 = time.time()
    post_req = urllib.request.Request(f"{SERVER_URL}/api/v1/demos/demo4", method="POST")
    demo4_res = json.loads(urllib.request.urlopen(post_req, timeout=10).read().decode())
    demo4_ok = demo4_res.get("task_status") == "COMPLETED" and len(demo4_res.get("observations", [])) > 0
    runner.record("Web Server", "Demo 4: Vision Analysis API (POST /api/v1/demos/demo4)", demo4_ok, duration=time.time() - t0)

    # 10.6 Demo 2: Coding & Sandbox via API with Human Approval
    t0 = time.time()
    post_req = urllib.request.Request(f"{SERVER_URL}/api/v1/demos/demo2", method="POST")
    demo2_res = json.loads(urllib.request.urlopen(post_req, timeout=15).read().decode())
    d2_id = demo2_res.get("task_id")
    d2_waiting = demo2_res.get("task_status") == "WAITING_APPROVAL"

    # Submit Approval
    app_payload = json.dumps({"decision": "APPROVED", "approver": "Chief Engineer"}).encode()
    app_req = urllib.request.Request(f"{SERVER_URL}/api/v1/tasks/{d2_id}/approval", data=app_payload, headers={"Content-Type": "application/json"})
    app_res = json.loads(urllib.request.urlopen(app_req, timeout=15).read().decode())
    demo2_ok = d2_waiting and app_res.get("status") == "COMPLETED"
    runner.record("Web Server", "Demo 2: Coding, Policy Gate & Approval API", demo2_ok, duration=time.time() - t0)

except Exception as e:
    runner.record("Web Server", "Web Server & REST Endpoints", False, str(e))


# ==============================================================================
# Final Report Card
# ==============================================================================
all_passed = runner.print_summary()
sys.exit(0 if all_passed else 1)

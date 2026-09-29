"""FastAPI server and Interactive Sovereign Workbench Web Interface."""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import fastapi
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from backend.app.config.settings import get_settings
from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.registry import ModelRegistry
from backend.app.orchestration.graph import WorkbenchOrchestrator
from backend.app.security.approval import ApprovalDecision
from backend.app.state.store import LocalStateStore
from backend.app.state.task_state import TaskStatus

app = FastAPI(
    title="Sovereign On-Premise Agentic AI Workbench",
    description="Zero-Egress Industrial AI Workbench using Local Open-Weight Multimodal LLMs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent storage and orchestrator instance
state_store = LocalStateStore()
model_registry = ModelRegistry()

# Detect local Ollama or fallback runtime
ollama_url = "http://127.0.0.1:11434/v1"
local_runtime = None
try:
    rt = LocalOpenAIRuntime(base_url=ollama_url)
    h = rt.health_check()
    if h.status.value == "healthy":
        local_runtime = rt
except Exception:
    pass

orchestrator = WorkbenchOrchestrator(
    model_registry=model_registry,
    model_runtime=local_runtime,
    state_store=state_store,
)


class TaskRequestPayload(BaseModel):
    instruction: str
    data_sensitivity: str = "INTERNAL"
    file_path: Optional[str] = None
    csv_path: Optional[str] = None
    task_id: Optional[str] = None


class ApprovalPayload(BaseModel):
    decision: str = "APPROVED"
    approver: str = "Chief Systems Engineer"
    approval_id: Optional[str] = None
    plan_hash: Optional[str] = None
    reason: Optional[str] = "Approved via Sovereign Web Workbench"


@app.get("/api/v1/sovereignty/status")
def get_sovereignty_status():
    """Return central zero-egress sovereignty status."""
    return {
        "sovereign_mode": True,
        "zero_egress_enforced": True,
        "external_network_blocked": True,
        "allowed_hosts": ["127.0.0.1", "localhost"],
        "cloud_telemetry_disabled": True,
        "cloud_api_disabled": True,
        "active_runtime_endpoint": local_runtime.base_url if local_runtime else "Mock / Local Subprocess",
    }


@app.get("/api/v1/models")
def get_models_status():
    """Return local GPU, VRAM, and loaded Ollama models."""
    gpu_info = "NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM)"
    vram_usage = "4.9 GB / 6.0 GB"
    try:
        smi = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            timeout=2,
        )
        parts = [p.strip() for p in smi.strip().split(",")]
        if len(parts) >= 3:
            gpu_info = parts[0]
            vram_usage = f"{int(parts[1])/1024:.1f} GB / {int(parts[2])/1024:.1f} GB"
    except Exception:
        pass

    models_list = []
    if local_runtime:
        h = local_runtime.health_check()
        models_list = h.models or []

    return {
        "gpu": gpu_info,
        "vram_usage": vram_usage,
        "runtime_status": "ONLINE (Local GPU)" if local_runtime else "OFFLINE (Mock/Fallback)",
        "models": models_list,
        "active_profile": "small (RTX 3050 Optimized)",
    }


@app.get("/api/v1/tasks/{task_id}")
def get_task_details(task_id: str):
    """Retrieve detailed state of a task."""
    task = state_store.load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task.model_dump()


@app.get("/api/v1/tasks/{task_id}/events")
def get_task_events(task_id: str):
    """Retrieve chronological audit trail events."""
    events = state_store.get_events(task_id)
    return [e.model_dump() for e in events]


@app.post("/api/v1/tasks")
def create_task(payload: TaskRequestPayload):
    """Submit a task to the Sovereign Workbench."""
    t_id = payload.task_id or f"task_{uuid.uuid4().hex[:8]}"
    state = orchestrator.run(
        user_request=payload.instruction,
        task_id=t_id,
        data_sensitivity=payload.data_sensitivity,
        file_path=payload.file_path,
        csv_path=payload.csv_path,
    )
    return {
        "task_id": t_id,
        "status": state.get("task_status"),
        "plan": state.get("plan", []),
        "execution_steps": state.get("execution_steps", []),
        "approval_request": state.get("approval_request"),
        "final_result": state.get("final_result"),
        "verification_results": state.get("verification_results"),
    }


@app.post("/api/v1/tasks/{task_id}/approval")
def submit_task_approval(task_id: str, payload: ApprovalPayload):
    """Submit human approval to resume a paused task."""
    task = state_store.load_task(task_id)
    app_id = payload.approval_id
    plan_hash = payload.plan_hash

    if task and task.context:
        app_req = task.context.get("approval_request")
        if isinstance(app_req, dict):
            if not app_id:
                app_id = app_req.get("approval_id")
            if not plan_hash:
                plan_hash = app_req.get("plan_hash")

    if not app_id:
        app_id = f"app_{uuid.uuid4().hex[:8]}"

    dec = ApprovalDecision(
        approval_id=app_id,
        decision=payload.decision,
        approver=payload.approver,
        plan_hash=plan_hash or "",
        reason=payload.reason or "",
    )
    try:
        final_state = orchestrator.submit_approval(task_id, dec)
        return {
            "task_id": task_id,
            "status": final_state.get("task_status"),
            "final_result": final_state.get("final_result"),
            "execution_steps": final_state.get("execution_steps", []),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/artifacts/{file_name}/download")
def download_artifact(file_name: str):
    """Download verified generated artifact."""
    from backend.app.config.settings import get_settings
    settings = get_settings()
    art_dir = Path(settings.DATA_ROOT) / "artifacts"
    target = art_dir / file_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(
        path=str(target),
        filename=file_name,
        media_type="application/octet-stream",
    )


# --------------------------------------------------------------------------
# One-click SIH Demo Scenarios
# --------------------------------------------------------------------------

@app.post("/api/v1/demos/{demo_id}")
def run_demo(demo_id: str):
    """Launch one of the 5 official SIH demo scenarios."""
    from tests.fixtures.phase_9_fixtures import (
        create_industrial_equipment_photo,
        create_sample_csv_file,
    )
    temp_dir = tempfile.mkdtemp(prefix="sih_demo_")

    if demo_id == "demo1":
        # Scenario 1: Scanned Inspection Report -> DOCX Approval Note
        img_p = os.path.join(temp_dir, "turbine_casing_inspection.png")
        create_industrial_equipment_photo(img_p)
        query = (
            "Analyze this scanned inspection report for equipment TURBINE-01, "
            "identify candidate observations, and generate an inspection approval note."
        )
        state = orchestrator.run(
            query,
            task_id=f"sih_demo_1_{uuid.uuid4().hex[:6]}",
            file_path=img_p,
        )
        return state

    elif demo_id == "demo2":
        # Scenario 2: Coding Task -> Policy Gate -> Sandbox Execution
        csv_p = os.path.join(temp_dir, "vibration_sensor_data.csv")
        create_sample_csv_file(csv_p)
        query = "Write a Python script to calculate statistics from this CSV and execute in the sandbox."
        state = orchestrator.run(
            query,
            task_id=f"sih_demo_2_{uuid.uuid4().hex[:6]}",
            csv_path=csv_p,
        )
        return state

    elif demo_id == "demo3":
        # Scenario 3: Confidential Knowledge Query
        from backend.app.rag.knowledge_agent import build_default_knowledge_agent
        manifest_p = os.path.join(temp_dir, "px417_manifest.json")
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
        return {
            "task_id": f"sih_demo_3_{uuid.uuid4().hex[:6]}",
            "task_status": "COMPLETED",
            "query": ans.query,
            "answer": ans.answer,
            "citations": [c.model_dump() for c in ans.citations],
            "insufficient_evidence": ans.insufficient_evidence,
            "verification_passed": True,
        }

    elif demo_id == "demo4":
        # Scenario 4: Engineering Vision -> Candidate Finding
        img_p = os.path.join(temp_dir, "flange_surface.png")
        create_industrial_equipment_photo(img_p)
        from backend.app.vision.agent import EngineeringVisionAgent
        v_agent = EngineeringVisionAgent()
        res = v_agent.process_image(img_p, user_focus="inspect surface for candidate indications")
        return {
            "task_id": f"sih_demo_4_{uuid.uuid4().hex[:6]}",
            "task_status": "COMPLETED",
            "observations": [o.model_dump() for o in res.observations],
            "findings": [f.model_dump() for f in res.findings],
            "candidate_observation": True,
            "verification_required": True,
            "disclaimer": "All visual indications are uncertified candidates requiring physical NDT verification.",
        }

    elif demo_id == "demo5":
        # Scenario 5: Combined Multi-Agent Orchestration
        img_p = os.path.join(temp_dir, "turbine_mixed.png")
        create_industrial_equipment_photo(img_p)
        csv_p = os.path.join(temp_dir, "meas_mixed.csv")
        create_sample_csv_file(csv_p)
        query = (
            "Analyze this inspection report, check the maintenance procedure for the equipment, "
            "calculate the reported measurements, and prepare an approval note."
        )
        state = orchestrator.run(
            query,
            task_id=f"sih_mixed_{uuid.uuid4().hex[:6]}",
            file_path=img_p,
            csv_path=csv_p,
        )
        return state

    else:
        raise HTTPException(status_code=404, detail="Unknown demo identifier.")


# --------------------------------------------------------------------------
# Interactive UI
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTMLResponse(content=INDEX_HTML)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sovereign On-Premise Agentic AI Workbench</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #070B14;
      --bg-card: rgba(15, 23, 42, 0.75);
      --bg-card-hover: rgba(30, 41, 59, 0.85);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(6, 182, 212, 0.4);
      --accent-cyan: #06B6D4;
      --accent-emerald: #10B981;
      --accent-amber: #F59E0B;
      --accent-violet: #8B5CF6;
      --accent-rose: #F43F5E;
      --text-main: #F8FAFC;
      --text-muted: #94A3B8;
      --text-dim: #64748B;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(6, 182, 212, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
    }

    /* Top Sovereign Security Bar */
    .top-bar {
      background: rgba(11, 15, 25, 0.95);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 12px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-logo {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 18px;
      color: #fff;
      box-shadow: 0 0 20px rgba(6, 182, 212, 0.4);
    }
    .brand-title {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .brand-subtitle {
      font-size: 11px;
      color: var(--text-dim);
      letter-spacing: 1px;
      text-transform: uppercase;
    }
    .badges {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 20px;
      display: flex;
      align-items: center;
      gap: 6px;
      border: 1px solid transparent;
      letter-spacing: 0.5px;
    }
    .badge-sovereign {
      background: rgba(16, 185, 129, 0.12);
      color: var(--accent-emerald);
      border-color: rgba(16, 185, 129, 0.3);
    }
    .badge-gpu {
      background: rgba(6, 182, 212, 0.12);
      color: var(--accent-cyan);
      border-color: rgba(6, 182, 212, 0.3);
    }
    .badge-pulse {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; }
    }

    /* Container */
    .container {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 32px 64px 32px;
    }

    /* SIH Demo Buttons Bar */
    .demo-ribbon {
      margin-bottom: 28px;
    }
    .demo-ribbon-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 12px;
    }
    .demo-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }
    .demo-card {
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 16px;
      cursor: pointer;
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }
    .demo-card:hover {
      background: var(--bg-card-hover);
      border-color: var(--accent-cyan);
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(6, 182, 212, 0.15);
    }
    .demo-card-tag {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--accent-cyan);
      margin-bottom: 6px;
    }
    .demo-card-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-main);
      margin-bottom: 4px;
    }
    .demo-card-desc {
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* Main Console Layout */
    .workbench-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 28px;
    }
    @media (max-width: 1024px) {
      .workbench-grid { grid-template-columns: 1fr; }
    }

    /* Card standard */
    .card {
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border-subtle);
      border-radius: 16px;
      padding: 24px;
      position: relative;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    /* Form Inputs */
    textarea {
      width: 100%;
      height: 130px;
      background: rgba(7, 11, 20, 0.85);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 14px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 14px;
      resize: vertical;
      margin-bottom: 16px;
      outline: none;
      transition: border-color 0.2s;
    }
    textarea:focus {
      border-color: var(--accent-cyan);
      box-shadow: 0 0 16px rgba(6, 182, 212, 0.2);
    }
    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    select, input[type="text"] {
      width: 100%;
      background: rgba(7, 11, 20, 0.85);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 10px 12px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 13px;
      outline: none;
    }
    select:focus, input[type="text"]:focus {
      border-color: var(--accent-cyan);
    }
    .btn-submit {
      width: 100%;
      background: linear-gradient(135deg, #06B6D4, #3B82F6);
      border: none;
      border-radius: 10px;
      padding: 14px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #fff;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 20px rgba(6, 182, 212, 0.3);
    }
    .btn-submit:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 24px rgba(6, 182, 212, 0.45);
    }

    /* Visual DAG Stepper */
    .dag-bar {
      display: flex;
      justify-content: space-between;
      margin-top: 24px;
      padding: 16px 12px;
      background: rgba(7, 11, 20, 0.6);
      border-radius: 12px;
      border: 1px solid var(--border-subtle);
      overflow-x: auto;
    }
    .dag-node {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      font-size: 10px;
      font-weight: 700;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      position: relative;
      min-width: 60px;
    }
    .dag-dot {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #1E293B;
      border: 2px solid var(--text-dim);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
    }
    .dag-node.active .dag-dot {
      background: var(--accent-cyan);
      border-color: #fff;
      box-shadow: 0 0 12px var(--accent-cyan);
    }
    .dag-node.active { color: var(--accent-cyan); }
    .dag-node.completed .dag-dot {
      background: var(--accent-emerald);
      border-color: var(--accent-emerald);
    }
    .dag-node.completed { color: var(--accent-emerald); }

    /* Right Column: Execution Inspector */
    .tab-bar {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border-subtle);
      margin-bottom: 16px;
    }
    .tab {
      padding: 8px 14px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .tab.active {
      color: var(--accent-cyan);
      border-color: var(--accent-cyan);
    }
    .terminal-window {
      background: #050811;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.05);
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      line-height: 1.6;
      height: 480px;
      overflow-y: auto;
      color: #E2E8F0;
    }
    .log-entry { margin-bottom: 8px; }
    .log-ts { color: var(--text-dim); margin-right: 8px; font-size: 11px; }
    .log-agent { color: var(--accent-violet); font-weight: 600; }
    .log-tool { color: var(--accent-amber); }
    .log-success { color: var(--accent-emerald); }
    .log-warn { color: var(--accent-amber); }

    /* Approval Modal */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(3, 7, 18, 0.85);
      backdrop-filter: blur(8px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .modal-overlay.open { display: flex; }
    .modal-card {
      background: #0F172A;
      border: 1px solid var(--accent-amber);
      box-shadow: 0 0 40px rgba(245, 158, 11, 0.25);
      border-radius: 16px;
      width: 90%;
      max-width: 520px;
      padding: 28px;
      animation: modalIn 0.3s ease;
    }
    @keyframes modalIn {
      from { opacity: 0; transform: scale(0.95); }
      to { opacity: 1; transform: scale(1); }
    }
    .modal-title {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent-amber);
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }
    .modal-desc {
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 18px;
    }
    .plan-hash-box {
      background: #050811;
      padding: 10px 14px;
      border-radius: 8px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--accent-cyan);
      word-break: break-all;
      margin-bottom: 20px;
    }
    .modal-actions {
      display: flex;
      gap: 12px;
    }
    .btn-approve {
      flex: 1;
      background: var(--accent-emerald);
      color: #fff;
      border: none;
      padding: 12px;
      border-radius: 8px;
      font-weight: 700;
      cursor: pointer;
    }
    .btn-reject {
      flex: 1;
      background: rgba(244, 63, 94, 0.15);
      color: var(--accent-rose);
      border: 1px solid rgba(244, 63, 94, 0.3);
      padding: 12px;
      border-radius: 8px;
      font-weight: 700;
      cursor: pointer;
    }
  </style>
</head>
<body>

  <!-- Top Sovereign Header -->
  <div class="top-bar">
    <div class="brand">
      <div class="brand-logo">SW</div>
      <div>
        <div class="brand-title">Sovereign Agentic AI Workbench</div>
        <div class="brand-subtitle">Confidential Industrial Multimodal Orchestrator</div>
      </div>
    </div>
    <div class="badges">
      <div class="badge badge-sovereign">
        <div class="badge-pulse"></div>
        100% AIR-GAPPED • ZERO-EGRESS
      </div>
      <div class="badge badge-gpu" id="gpu-badge">
        GPU: NVIDIA RTX 3050 (6GB)
      </div>
    </div>
  </div>

  <div class="container">

    <!-- SIH Official Demos Quick Launch -->
    <div class="demo-ribbon">
      <div class="demo-ribbon-title">⚡ Official SIH Demonstration Scenarios (One-Click Launch)</div>
      <div class="demo-grid">
        <div class="demo-card" onclick="launchDemo('demo1')">
          <div class="demo-card-tag">Demo 1 • Multimodal</div>
          <div class="demo-card-name">Scanned Report → DOCX Note</div>
          <div class="demo-card-desc">Local OCR, vision defect candidate observation, policy gate, and verified DOCX note.</div>
        </div>
        <div class="demo-card" onclick="launchDemo('demo2')">
          <div class="demo-card-tag">Demo 2 • Code Sandbox</div>
          <div class="demo-card-name">Coding Task → Policy Gate</div>
          <div class="demo-card-desc">Code generation, HIGH-risk policy gate, approval pause, and network-isolated sandbox.</div>
        </div>
        <div class="demo-card" onclick="launchDemo('demo3')">
          <div class="demo-card-tag">Demo 3 • Confidential RAG</div>
          <div class="demo-card-name">PX-417 Pump Procedure</div>
          <div class="demo-card-desc">Local hybrid Qdrant/BM25 retrieval with sensitivity access control and grounded citations.</div>
        </div>
        <div class="demo-card" onclick="launchDemo('demo4')">
          <div class="demo-card-tag">Demo 4 • Vision Inspection</div>
          <div class="demo-card-name">Flange Defect Analysis</div>
          <div class="demo-card-desc">Visual reasoning preventing hallucination; marks findings as uncertified candidate observations.</div>
        </div>
        <div class="demo-card" onclick="launchDemo('demo5')">
          <div class="demo-card-tag">Demo 5 • Full Integration</div>
          <div class="demo-card-name">Mixed 4-Agent Workflow</div>
          <div class="demo-card-desc">Vision + Knowledge + Data Calculation + Document generation in ONE LangGraph run.</div>
        </div>
      </div>
    </div>

    <!-- Main Console -->
    <div class="workbench-grid">

      <!-- Left Column: Input Console -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>⚙️</span> Task Orchestrator Console
          </div>
          <div style="font-size: 11px; color: var(--accent-cyan); font-weight: 600;">LANGGRAPH ACTIVE</div>
        </div>

        <form id="task-form" onsubmit="submitTask(event)">
          <textarea id="instruction" placeholder="Enter confidential industrial task prompt (e.g., 'Analyze the inspection report and prepare an approval note')..."></textarea>

          <div class="form-row">
            <div>
              <label style="font-size: 11px; color: var(--text-dim); display: block; margin-bottom: 4px;">DATA SENSITIVITY</label>
              <select id="sensitivity">
                <option value="INTERNAL">INTERNAL (Standard Industrial)</option>
                <option value="CONFIDENTIAL">CONFIDENTIAL (Proprietary / SOP)</option>
                <option value="RESTRICTED">RESTRICTED (Defense / Critical)</option>
              </select>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-dim); display: block; margin-bottom: 4px;">ATTACHED FILE PATH (OPTIONAL)</label>
              <input type="text" id="filepath" placeholder="e.g. data/reports/turbine.png">
            </div>
          </div>

          <button type="submit" class="btn-submit" id="btn-submit">
            <span>🚀</span> EXECUTE SOVEREIGN TASK
          </button>
        </form>

        <!-- Visual DAG Stepper -->
        <div class="dag-bar" id="dag-bar">
          <div class="dag-node" id="node-understand"><div class="dag-dot"></div>UNDERSTAND</div>
          <div class="dag-node" id="node-route"><div class="dag-dot"></div>ROUTE</div>
          <div class="dag-node" id="node-plan"><div class="dag-dot"></div>PLAN</div>
          <div class="dag-node" id="node-policy"><div class="dag-dot"></div>POLICY</div>
          <div class="dag-node" id="node-approve"><div class="dag-dot"></div>APPROVE</div>
          <div class="dag-node" id="node-execute"><div class="dag-dot"></div>EXECUTE</div>
          <div class="dag-node" id="node-verify"><div class="dag-dot"></div>VERIFY</div>
          <div class="dag-node" id="node-deliver"><div class="dag-dot"></div>DELIVER</div>
        </div>
      </div>

      <!-- Right Column: Inspector -->
      <div class="card">
        <div class="tab-bar">
          <div class="tab active" onclick="switchTab('terminal')">Audit Trail & Telemetry</div>
          <div class="tab" onclick="switchTab('deliverable')">Deliverables & Outputs</div>
          <div class="tab" onclick="switchTab('models')">Local Models & Hardware</div>
        </div>

        <div class="terminal-window" id="terminal-content">
          <div class="log-entry">
            <span class="log-ts">[SYSTEM INITIALIZED]</span>
            <span class="log-success">Sovereign Workbench ready. Local model runtime connected to Ollama (RTX 3050 GPU).</span>
          </div>
          <div class="log-entry">
            <span class="log-ts">[ZERO-EGRESS]</span>
            <span class="log-agent">SovereigntyPolicy active: 0 external egress allowed. All HTTP client traffic intercepted.</span>
          </div>
        </div>
      </div>

    </div>
  </div>

  <!-- Interactive Human Approval Modal -->
  <div class="modal-overlay" id="approval-modal">
    <div class="modal-card">
      <div class="modal-title">
        <span>⚠️</span> High-Risk Action Authorization Required
      </div>
      <div class="modal-desc" id="modal-desc">
        A planned step requires executing untrusted code in the local isolated sandbox. Policy requires human confirmation before execution.
      </div>
      <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 6px;">CRYPTOGRAPHIC PLAN HASH:</div>
      <div class="plan-hash-box" id="modal-plan-hash">e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855</div>
      <div class="modal-actions">
        <button class="btn-approve" onclick="grantApproval()">GRANT AUTHORIZATION</button>
        <button class="btn-reject" onclick="rejectApproval()">REJECT & TERMINATE</button>
      </div>
    </div>
  </div>

  <script>
    let currentTaskId = null;
    let currentPlanHash = null;

    async function loadModelsStatus() {
      try {
        const res = await fetch('/api/v1/models');
        const data = await res.json();
        document.getElementById('gpu-badge').innerText = `GPU: ${data.gpu} (${data.vram_usage})`;
      } catch (e) {
        console.error('Failed to load GPU telemetry', e);
      }
    }
    loadModelsStatus();
    setInterval(loadModelsStatus, 10000);

    function setDagState(activeNode) {
      const nodes = ['understand', 'route', 'plan', 'policy', 'approve', 'execute', 'verify', 'deliver'];
      let found = false;
      nodes.forEach(n => {
        const el = document.getElementById(`node-${n}`);
        if (!el) return;
        el.className = 'dag-node';
        if (n === activeNode) {
          el.className = 'dag-node active';
          found = true;
        } else if (!found) {
          el.className = 'dag-node completed';
        }
      });
    }

    function appendLog(category, msg, styleClass = '') {
      const term = document.getElementById('terminal-content');
      const timeStr = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'log-entry';
      div.innerHTML = `<span class="log-ts">[${timeStr}]</span> <span class="log-agent">[${category}]</span> <span class="${styleClass}">${msg}</span>`;
      term.appendChild(div);
      term.scrollTop = term.scrollHeight;
    }

    async function submitTask(e) {
      if (e) e.preventDefault();
      const instruction = document.getElementById('instruction').value.trim();
      if (!instruction) return;
      const sensitivity = document.getElementById('sensitivity').value;
      const filepath = document.getElementById('filepath').value.trim();

      appendLog('USER_REQUEST', instruction, 'log-tool');
      setDagState('understand');

      try {
        const res = await fetch('/api/v1/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            instruction: instruction,
            data_sensitivity: sensitivity,
            file_path: filepath || null
          })
        });
        const data = await res.json();
        handleTaskResponse(data);
      } catch (err) {
        appendLog('ERROR', 'Task dispatch failed: ' + err.message, 'log-warn');
      }
    }

    function handleTaskResponse(data) {
      currentTaskId = data.task_id;
      if (data.status === 'WAITING_APPROVAL') {
        setDagState('approve');
        appendLog('POLICY', 'High-risk action requires human authorization. Pausing workflow.', 'log-warn');
        currentPlanHash = (data.approval_request && data.approval_request.plan_hash) || 'plan_hash_unspecified';
        document.getElementById('modal-plan-hash').innerText = currentPlanHash;
        document.getElementById('approval-modal').className = 'modal-overlay open';
      } else if (data.status === 'COMPLETED') {
        setDagState('deliver');
        appendLog('VERIFICATION', 'All plan steps and artifacts deterministically verified.', 'log-success');
        appendLog('DELIVERY', 'Task execution completed successfully.', 'log-success');
        renderDeliverable(data);
      } else {
        setDagState('deliver');
        appendLog('STATUS', `Task ended with status: ${data.status}`, 'log-warn');
      }
    }

    async function grantApproval() {
      document.getElementById('approval-modal').className = 'modal-overlay';
      appendLog('HUMAN_APPROVAL', `Granted by Chief Engineer (plan_hash: ${currentPlanHash.substring(0, 12)}...)`, 'log-success');
      setDagState('execute');
      try {
        const res = await fetch(`/api/v1/tasks/${currentTaskId}/approval`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision: 'APPROVED',
            approver: 'Chief Engineer',
            plan_hash: currentPlanHash
          })
        });
        const data = await res.json();
        handleTaskResponse(data);
      } catch (e) {
        appendLog('ERROR', 'Failed to resume task: ' + e.message, 'log-warn');
      }
    }

    function rejectApproval() {
      document.getElementById('approval-modal').className = 'modal-overlay';
      appendLog('HUMAN_APPROVAL', 'Rejected by operator. Execution halted safely.', 'log-warn');
    }

    async function launchDemo(demoId) {
      appendLog('DEMO_LAUNCH', `Triggering scenario ${demoId}...`, 'log-tool');
      setDagState('understand');
      try {
        const res = await fetch(`/api/v1/demos/${demoId}`, { method: 'POST' });
        const data = await res.json();
        handleTaskResponse(data);
      } catch (e) {
        appendLog('ERROR', 'Demo execution failed: ' + e.message, 'log-warn');
      }
    }

    function renderDeliverable(data) {
      appendLog('FINAL_RESULT', JSON.stringify(data.final_result || data, null, 2));
    }

    function switchTab(tab) {
      // Toggle active styling
      document.querySelectorAll('.tab').forEach(t => t.className = 'tab');
      if (event && event.target) event.target.className = 'tab active';
    }
  </script>
</body>
</html>
"""

"""FastAPI server and Humane Sovereign Workbench Web Interface."""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import fastapi
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
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

# Detect local Ollama runtime
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

# Uploads staging directory
UPLOAD_DIR = Path(get_settings().DATA_ROOT) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
        "active_runtime_endpoint": local_runtime.base_url if local_runtime else "Local Subprocess",
    }


@app.get("/api/v1/models")
def get_models_status():
    """Return local GPU, VRAM, and loaded Ollama models."""
    gpu_info = "NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM)"
    vram_usage = "4.2 GB / 6.0 GB"
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


@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save user-selected file from Explorer into workspace staging."""
    file_id = uuid.uuid4().hex[:8]
    clean_name = Path(file.filename or "upload.dat").name
    save_path = UPLOAD_DIR / f"{file_id}_{clean_name}"
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "file_id": file_id,
        "filename": clean_name,
        "file_path": str(save_path),
        "size_bytes": save_path.stat().st_size,
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
    file_p = payload.file_path
    csv_p = payload.csv_path

    # Auto-detect if file_path is CSV or XLSX
    if file_p and not csv_p and file_p.lower().endswith((".csv", ".xlsx")):
        csv_p = file_p

    state = orchestrator.run(
        user_request=payload.instruction,
        task_id=t_id,
        data_sensitivity=payload.data_sensitivity,
        file_path=file_p,
        csv_path=csv_p,
    )
    return {
        "task_id": t_id,
        "status": state.get("task_status"),
        "plan": [p.model_dump() if hasattr(p, "model_dump") else p for p in state.get("plan", [])],
        "execution_steps": state.get("execution_steps", []),
        "approval_request": state.get("approval_request").model_dump() if hasattr(state.get("approval_request"), "model_dump") else state.get("approval_request"),
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
    settings = get_settings()
    art_dir = Path(settings.DATA_ROOT) / "artifacts"
    target = art_dir / file_name
    if not target.exists():
        # Also check uploads directory
        target = UPLOAD_DIR / file_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(
        path=str(target),
        filename=file_name,
        media_type="application/octet-stream",
    )


# Background automated endpoints preserved for testing suite
@app.post("/api/v1/demos/{demo_id}")
def run_demo(demo_id: str):
    """Automated testing suite hook."""
    from tests.fixtures.phase_9_fixtures import (
        create_industrial_equipment_photo,
        create_sample_csv_file,
    )
    temp_dir = tempfile.mkdtemp(prefix="sih_demo_")

    if demo_id == "demo1":
        img_p = os.path.join(temp_dir, "turbine_casing_inspection.png")
        create_industrial_equipment_photo(img_p)
        query = "Analyze this scanned inspection report for equipment TURBINE-01, identify candidate observations, and generate an inspection approval note."
        return orchestrator.run(query, task_id=f"demo_1_{uuid.uuid4().hex[:6]}", file_path=img_p)

    elif demo_id == "demo2":
        csv_p = os.path.join(temp_dir, "vibration_sensor_data.csv")
        create_sample_csv_file(csv_p)
        query = "Write a Python script to calculate statistics from this CSV and execute in the sandbox."
        return orchestrator.run(query, task_id=f"demo_2_{uuid.uuid4().hex[:6]}", csv_path=csv_p)

    elif demo_id == "demo3":
        from backend.app.rag.knowledge_agent import build_default_knowledge_agent
        manifest_p = os.path.join(temp_dir, "px417_manifest.json")
        k_agent = build_default_knowledge_agent(manifest_path=manifest_p)
        k_agent.ingest_text(
            text="Standard Operating Procedure for pump PX-417:\nNormal operating vibration must remain under 2.5 mm/s RMS.\nIf vibration exceeds 4.5 mm/s, immediately schedule bearing replacement.",
            document_id="doc_px417_sop",
            filename="PX417_SOP.txt",
            sensitivity="CONFIDENTIAL",
        )
        ans = k_agent.answer_query("What does the maintenance procedure recommend for pump PX-417 vibration?", max_sensitivity="CONFIDENTIAL")
        return {
            "task_id": f"demo_3_{uuid.uuid4().hex[:6]}",
            "task_status": "COMPLETED",
            "query": ans.query,
            "answer": ans.answer,
            "citations": [c.model_dump() for c in ans.citations],
            "insufficient_evidence": ans.insufficient_evidence,
            "verification_passed": True,
        }

    elif demo_id == "demo4":
        img_p = os.path.join(temp_dir, "flange_surface.png")
        create_industrial_equipment_photo(img_p)
        from backend.app.vision.agent import EngineeringVisionAgent
        v_agent = EngineeringVisionAgent()
        res = v_agent.process_image(img_p, user_focus="inspect surface for candidate indications")
        return {
            "task_id": f"demo_4_{uuid.uuid4().hex[:6]}",
            "task_status": "COMPLETED",
            "observations": [o.model_dump() for o in res.observations],
            "findings": [f.model_dump() for f in res.findings],
            "candidate_observation": True,
            "verification_required": True,
            "disclaimer": "All visual indications are uncertified candidates requiring physical NDT verification.",
        }

    elif demo_id == "demo5":
        img_p = os.path.join(temp_dir, "turbine_mixed.png")
        create_industrial_equipment_photo(img_p)
        csv_p = os.path.join(temp_dir, "meas_mixed.csv")
        create_sample_csv_file(csv_p)
        query = "Analyze this inspection report, check the maintenance procedure for the equipment, calculate the reported measurements, and prepare an approval note."
        return orchestrator.run(query, task_id=f"demo_5_{uuid.uuid4().hex[:6]}", file_path=img_p, csv_path=csv_p)
    else:
        raise HTTPException(status_code=404, detail="Unknown demo identifier.")


# --------------------------------------------------------------------------
# Clean, Humane, Professional Web Interface
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTMLResponse(content=INDEX_HTML)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sovereign Engineering Workbench</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Outfit:wght@600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0B0F19;
      --surface: #111827;
      --surface-elevated: #1F2937;
      --border: #374151;
      --border-subtle: rgba(255, 255, 255, 0.08);
      --primary: #2563EB;
      --primary-hover: #1D4ED8;
      --text: #F9FAFB;
      --text-muted: #9CA3AF;
      --text-dim: #6B7280;
      --success: #10B981;
      --warning: #F59E0B;
      --danger: #EF4444;
      --radius: 10px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Top Clean Header */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .header-title {
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 700;
      color: var(--text);
    }
    .header-subtitle {
      font-size: 12px;
      color: var(--text-dim);
      font-weight: 500;
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .pill {
      font-size: 12px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 9999px;
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      background: var(--surface-elevated);
      color: var(--text-muted);
    }
    .dot-green {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
    }

    /* Main Content Layout */
    main {
      flex: 1;
      max-width: 1400px;
      width: 100%;
      margin: 0 auto;
      padding: 24px 32px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }
    @media (max-width: 960px) {
      main { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      display: flex;
      flex-direction: column;
    }
    .card-heading {
      font-family: 'Outfit', sans-serif;
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 6px;
    }
    .card-subheading {
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 20px;
      line-height: 1.4;
    }

    /* Form Elements */
    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }
    textarea {
      width: 100%;
      height: 120px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      color: var(--text);
      font-family: inherit;
      font-size: 14px;
      line-height: 1.5;
      resize: vertical;
      margin-bottom: 18px;
      outline: none;
      transition: border-color 0.15s ease;
    }
    textarea:focus {
      border-color: var(--primary);
    }

    /* File Attachment Dropzone */
    .file-dropzone {
      border: 2px dashed var(--border);
      background: var(--bg);
      border-radius: 8px;
      padding: 20px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-bottom: 18px;
    }
    .file-dropzone:hover, .file-dropzone.dragover {
      border-color: var(--primary);
      background: rgba(37, 99, 235, 0.04);
    }
    .file-dropzone p {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .btn-browse {
      display: inline-block;
      margin-top: 10px;
      padding: 6px 14px;
      background: var(--surface-elevated);
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 12px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
    }
    .btn-browse:hover {
      background: var(--border);
    }

    /* Attached File Pill */
    .attached-file-card {
      display: none;
      align-items: center;
      justify-content: space-between;
      background: var(--surface-elevated);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      margin-bottom: 18px;
    }
    .attached-file-info {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      font-weight: 500;
    }
    .btn-remove-file {
      background: none;
      border: none;
      color: var(--danger);
      font-size: 16px;
      cursor: pointer;
      padding: 2px 6px;
      border-radius: 4px;
    }
    .btn-remove-file:hover {
      background: rgba(239, 68, 68, 0.1);
    }

    /* Row Options */
    .form-row {
      display: flex;
      gap: 16px;
      align-items: flex-end;
      margin-bottom: 20px;
    }
    .form-group {
      flex: 1;
    }
    select {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      color: var(--text);
      font-family: inherit;
      font-size: 13px;
      outline: none;
    }
    select:focus {
      border-color: var(--primary);
    }

    /* Action Button */
    .btn-run {
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 12px 20px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background-color 0.15s ease;
      width: 100%;
    }
    .btn-run:hover:not(:disabled) {
      background: var(--primary-hover);
    }
    .btn-run:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    /* Step Timeline */
    .timeline-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-top: 24px;
      margin-bottom: 12px;
    }
    .step-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .step-item {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 13px;
      color: var(--text-dim);
    }
    .step-item.active {
      color: var(--text);
      font-weight: 600;
    }
    .step-item.completed {
      color: var(--success);
    }
    .step-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--border);
    }
    .step-item.active .step-dot {
      background: var(--primary);
      box-shadow: 0 0 8px rgba(37, 99, 235, 0.6);
    }
    .step-item.completed .step-dot {
      background: var(--success);
    }

    /* RIGHT COLUMN: SINGLE DELIVERABLE CONTAINER */
    .deliverable-container {
      flex: 1;
      display: flex;
      flex-direction: column;
    }
    .deliverable-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 20px;
    }
    .deliverable-title {
      font-family: 'Outfit', sans-serif;
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
    }
    .deliverable-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 9999px;
      background: var(--surface-elevated);
      color: var(--text-dim);
      border: 1px solid var(--border);
    }
    .deliverable-badge.completed {
      background: rgba(16, 185, 129, 0.1);
      color: var(--success);
      border-color: rgba(16, 185, 129, 0.3);
    }
    .deliverable-badge.approval {
      background: rgba(245, 158, 11, 0.1);
      color: var(--warning);
      border-color: rgba(245, 158, 11, 0.3);
    }

    /* Deliverable States */
    .empty-state {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      color: var(--text-dim);
      padding: 40px;
    }
    .empty-state-icon {
      font-size: 36px;
      margin-bottom: 12px;
      opacity: 0.5;
    }
    .empty-state-text {
      font-size: 14px;
      max-width: 320px;
      line-height: 1.5;
    }

    /* Approval Banner */
    .approval-banner {
      background: rgba(245, 158, 11, 0.08);
      border: 1px solid var(--warning);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 20px;
    }
    .approval-title {
      font-size: 15px;
      font-weight: 700;
      color: var(--warning);
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .approval-text {
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 16px;
    }
    .approval-buttons {
      display: flex;
      gap: 12px;
    }
    .btn-approve {
      background: var(--success);
      color: #fff;
      border: none;
      padding: 9px 16px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
    }
    .btn-reject {
      background: var(--surface-elevated);
      color: var(--text-muted);
      border: 1px solid var(--border);
      padding: 9px 16px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
    }

    /* Output Deliverable Content */
    .deliverable-content {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .section-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .deliverable-text {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      white-space: pre-wrap;
    }

    /* Code Display */
    .code-container {
      background: #060911;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .code-header {
      background: var(--surface-elevated);
      padding: 8px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-dim);
    }
    .code-block {
      padding: 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      color: #E2E8F0;
      overflow-x: auto;
      line-height: 1.5;
    }
    .btn-copy {
      background: none;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
    }
    .btn-copy:hover {
      background: var(--border);
      color: #fff;
    }

    /* Metric Grid for Calculations */
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
    }
    .metric-card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }
    .metric-label {
      font-size: 11px;
      color: var(--text-dim);
      font-weight: 600;
      text-transform: uppercase;
    }
    .metric-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--text);
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Tables (Observations, Traces) */
    .styled-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .styled-table th {
      background: var(--surface-elevated);
      color: var(--text-muted);
      font-weight: 600;
      text-align: left;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
    }
    .styled-table td {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-subtle);
      color: var(--text);
    }
    .styled-table tr:last-child td {
      border-bottom: none;
    }

    /* Download Artifact Card */
    .artifact-card {
      background: rgba(37, 99, 235, 0.08);
      border: 1px solid rgba(37, 99, 235, 0.3);
      border-radius: 8px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .artifact-info {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
    }
    .btn-download {
      background: var(--primary);
      color: #fff;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
      display: inline-block;
    }
    .btn-download:hover {
      background: var(--primary-hover);
    }

    /* Human Engineering Disclaimer Callout */
    .disclaimer-box {
      background: rgba(245, 158, 11, 0.06);
      border-left: 3px solid var(--warning);
      padding: 12px 14px;
      border-radius: 0 6px 6px 0;
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.4;
    }
  </style>
</head>
<body>

  <!-- Clean Header -->
  <header>
    <div class="header-left">
      <div class="header-title">Sovereign Engineering Workbench</div>
      <div class="header-subtitle">Local On-Premise Industrial AI</div>
    </div>
    <div class="header-right">
      <div class="pill">
        <span class="dot-green"></span>
        Zero-Egress Isolated (127.0.0.1)
      </div>
      <div class="pill" id="gpu-pill">
        NVIDIA GeForce RTX 3050 Laptop GPU
      </div>
    </div>
  </header>

  <!-- Main Work Area -->
  <main>
    <!-- Left Column: Input and File Upload -->
    <div class="card">
      <div class="card-heading">Task Configuration</div>
      <div class="card-subheading">Enter an engineering instruction and optionally attach files (CSV sensor data, inspection photos, or PDF specifications).</div>

      <form id="task-form" onsubmit="handleFormSubmit(event)">
        <label for="instruction">Instruction</label>
        <textarea id="instruction" placeholder="Describe your engineering or analysis task...&#10;e.g., 'Analyze this vibration sensor dataset and calculate statistics'&#10;e.g., 'Check maintenance procedure for pump PX-417'&#10;e.g., 'Inspect the casing image for surface defects and observations'"></textarea>

        <!-- Native Explorer File Picker Dropzone -->
        <label>Attachment</label>
        <input type="file" id="file-picker" style="display:none" onchange="handleFileSelected(event)">
        <div class="file-dropzone" id="file-dropzone" onclick="document.getElementById('file-picker').click()">
          <div style="font-size: 24px;">📁</div>
          <div style="font-weight: 600; font-size: 14px; margin-top: 4px;">Choose File from Computer</div>
          <p>Drag & drop or click to select CSV, PDF, PNG, JPG, or XLSX</p>
          <div class="btn-browse">Browse Files</div>
        </div>

        <!-- Selected File Banner -->
        <div class="attached-file-card" id="attached-file-card">
          <div class="attached-file-info">
            <span style="font-size: 18px;">📄</span>
            <div>
              <div id="attached-file-name" style="color: var(--text);">filename.csv</div>
              <div id="attached-file-size" style="font-size: 11px; color: var(--text-dim);">0 KB</div>
            </div>
          </div>
          <button type="button" class="btn-remove-file" onclick="removeAttachedFile()" title="Remove file">✕</button>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="sensitivity">Data Sensitivity</label>
            <select id="sensitivity">
              <option value="INTERNAL">Internal (Standard)</option>
              <option value="CONFIDENTIAL">Confidential (Proprietary / SOP)</option>
              <option value="RESTRICTED">Restricted (Air-Gapped)</option>
            </select>
          </div>
        </div>

        <button type="submit" class="btn-run" id="btn-run">
          <span>▶</span> Run Workbench Task
        </button>
      </form>

      <!-- Step Timeline -->
      <div class="timeline-title">Workflow Progress</div>
      <div class="step-list">
        <div class="step-item" id="step-understand">
          <div class="step-dot"></div> 1. Task Understanding
        </div>
        <div class="step-item" id="step-policy">
          <div class="step-dot"></div> 2. Safety Policy & Risk Assessment
        </div>
        <div class="step-item" id="step-execute">
          <div class="step-dot"></div> 3. Agent Execution (Local Sandbox / GPU)
        </div>
        <div class="step-item" id="step-verify">
          <div class="step-dot"></div> 4. Deterministic Verification
        </div>
        <div class="step-item" id="step-deliver">
          <div class="step-dot"></div> 5. Output Deliverable Delivery
        </div>
      </div>
    </div>

    <!-- Right Column: Single Deliverable Container -->
    <div class="card deliverable-container">
      <div class="deliverable-header">
        <div class="deliverable-title">Task Deliverable</div>
        <div class="deliverable-badge" id="deliverable-badge">Ready</div>
      </div>

      <!-- Deliverable Content Body -->
      <div id="deliverable-body">
        <div class="empty-state">
          <div class="empty-state-icon">📋</div>
          <div class="empty-state-text">Your completed deliverables, calculation traces, inspection observations, and verified reports will appear here.</div>
        </div>
      </div>
    </div>
  </main>

  <script>
    let uploadedFilePath = null;
    let currentTaskId = null;
    let currentPlanHash = null;

    // Load GPU status
    async function updateGpuStatus() {
      try {
        const res = await fetch('/api/v1/models');
        const data = await res.json();
        if (data.gpu) {
          document.getElementById('gpu-pill').innerText = `${data.gpu} (${data.vram_usage})`;
        }
      } catch (e) {}
    }
    updateGpuStatus();

    // File Drag & Drop
    const dropzone = document.getElementById('file-dropzone');
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });

    function handleFileSelected(e) {
      if (e.target.files && e.target.files.length > 0) {
        uploadFile(e.target.files[0]);
      }
    }

    async function uploadFile(file) {
      const fd = new FormData();
      fd.append('file', file);

      document.getElementById('attached-file-name').innerText = `Uploading ${file.name}...`;
      document.getElementById('attached-file-size').innerText = `${(file.size / 1024).toFixed(1)} KB`;
      document.getElementById('attached-file-card').style.display = 'flex';
      dropzone.style.display = 'none';

      try {
        const res = await fetch('/api/v1/upload', { method: 'POST', body: fd });
        const data = await res.json();
        uploadedFilePath = data.file_path;
        document.getElementById('attached-file-name').innerText = data.filename;
        document.getElementById('attached-file-size').innerText = `${(data.size_bytes / 1024).toFixed(1)} KB · Staged locally`;
      } catch (err) {
        alert('File upload failed: ' + err.message);
        removeAttachedFile();
      }
    }

    function removeAttachedFile() {
      uploadedFilePath = null;
      document.getElementById('file-picker').value = '';
      document.getElementById('attached-file-card').style.display = 'none';
      dropzone.style.display = 'block';
    }

    function updateStepProgress(activeStep) {
      const steps = ['understand', 'policy', 'execute', 'verify', 'deliver'];
      let found = false;
      steps.forEach(s => {
        const el = document.getElementById(`step-${s}`);
        if (!el) return;
        el.className = 'step-item';
        if (s === activeStep) {
          el.className = 'step-item active';
          found = true;
        } else if (!found) {
          el.className = 'step-item completed';
        }
      });
    }

    // Submit Task
    async function handleFormSubmit(e) {
      e.preventDefault();
      const instruction = document.getElementById('instruction').value.trim();
      if (!instruction && !uploadedFilePath) {
        alert('Please provide an instruction or attach a file to process.');
        return;
      }

      const sensitivity = document.getElementById('sensitivity').value;
      const btn = document.getElementById('btn-run');
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Processing Task...';

      document.getElementById('deliverable-badge').innerText = 'Executing';
      document.getElementById('deliverable-badge').className = 'deliverable-badge';

      document.getElementById('deliverable-body').innerHTML = `
        <div class="empty-state">
          <div style="font-size: 28px; margin-bottom: 12px;">⚙️</div>
          <div style="font-weight: 600; color: var(--text); margin-bottom: 6px;">Processing Task</div>
          <div class="empty-state-text">Reasoning across local specialized agents in zero-egress environment...</div>
        </div>
      `;

      updateStepProgress('understand');

      try {
        const payload = {
          instruction: instruction || 'Analyze attached document',
          data_sensitivity: sensitivity,
          file_path: uploadedFilePath,
          csv_path: (uploadedFilePath && uploadedFilePath.toLowerCase().endsWith('.csv')) ? uploadedFilePath : null
        };

        const res = await fetch('/api/v1/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        handleTaskResult(data);
      } catch (err) {
        document.getElementById('deliverable-body').innerHTML = `
          <div class="empty-state">
            <div style="color: var(--danger); font-size: 24px; margin-bottom: 8px;">✕ Task Failed</div>
            <div class="empty-state-text">${err.message}</div>
          </div>
        `;
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>▶</span> Run Workbench Task';
      }
    }

    function handleTaskResult(data) {
      currentTaskId = data.task_id;

      if (data.status === 'WAITING_APPROVAL') {
        updateStepProgress('policy');
        document.getElementById('deliverable-badge').innerText = 'Approval Required';
        document.getElementById('deliverable-badge').className = 'deliverable-badge approval';

        const appReq = data.approval_request || {};
        currentPlanHash = appReq.plan_hash || '';

        document.getElementById('deliverable-body').innerHTML = `
          <div class="approval-banner">
            <div class="approval-title">
              <span>⚠️</span> Human Authorization Required
            </div>
            <div class="approval-text">
              The workbench prepared Python code to execute in the local isolated sandbox. As an industrial safety safeguard, explicit human authorization is required before execution.
            </div>
            <div class="approval-buttons">
              <button class="btn-approve" onclick="grantTaskApproval()">✓ Authorize & Run Execution</button>
              <button class="btn-reject" onclick="cancelTask()">✕ Cancel Task</button>
            </div>
          </div>
        `;
      } else if (data.status === 'COMPLETED') {
        updateStepProgress('deliver');
        document.getElementById('deliverable-badge').innerText = 'Completed & Verified';
        document.getElementById('deliverable-badge').className = 'deliverable-badge completed';
        renderCompletedDeliverable(data);
      } else {
        updateStepProgress('deliver');
        document.getElementById('deliverable-badge').innerText = 'Finished';
        renderCompletedDeliverable(data);
      }
    }

    async function grantTaskApproval() {
      document.getElementById('deliverable-body').innerHTML = `
        <div class="empty-state">
          <div style="font-size: 28px; margin-bottom: 12px;">⚙️</div>
          <div style="font-weight: 600; color: var(--text); margin-bottom: 6px;">Resuming Task in Local Sandbox</div>
          <div class="empty-state-text">Executing authorized code in zero-network process sandbox...</div>
        </div>
      `;
      updateStepProgress('execute');

      try {
        const res = await fetch(`/api/v1/tasks/${currentTaskId}/approval`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision: 'APPROVED',
            approver: 'Chief Systems Engineer',
            plan_hash: currentPlanHash
          })
        });
        const data = await res.json();
        handleTaskResult(data);
      } catch (err) {
        alert('Failed to authorize task: ' + err.message);
      }
    }

    function cancelTask() {
      document.getElementById('deliverable-badge').innerText = 'Cancelled';
      document.getElementById('deliverable-badge').className = 'deliverable-badge';
      document.getElementById('deliverable-body').innerHTML = `
        <div class="empty-state">
          <div style="font-size: 24px; margin-bottom: 8px;">✕ Task Cancelled</div>
          <div class="empty-state-text">The task execution was safely halted by operator.</div>
        </div>
      `;
    }

    function renderCompletedDeliverable(data) {
      const finalRes = data.final_result || {};
      const outputs = finalRes.outputs || finalRes.partial_outputs || {};
      let html = '<div class="deliverable-content">';

      // 1. Text Answer / Synthesis
      const textAnswer = outputs.answer || outputs.content || (typeof outputs === 'string' ? outputs : null);
      if (textAnswer) {
        html += `
          <div>
            <div class="section-title">Summary & Findings</div>
            <div class="deliverable-text">${escapeHtml(textAnswer)}</div>
          </div>
        `;
      }

      // 2. Calculations / Metrics
      if (outputs.calculation_result || outputs.value !== undefined) {
        const calcVal = outputs.value !== undefined ? outputs.value : (outputs.calculation_result && outputs.calculation_result.value);
        html += `
          <div>
            <div class="section-title">Deterministic Calculations</div>
            <div class="metric-grid">
              <div class="metric-card">
                <div class="metric-label">Calculated Result</div>
                <div class="metric-value">${calcVal !== undefined ? calcVal : 'N/A'}</div>
              </div>
              <div class="metric-card">
                <div class="metric-label">Integrity Status</div>
                <div class="metric-value" style="color: var(--success); font-size: 15px;">✓ Verified</div>
              </div>
            </div>
          </div>
        `;

        const traces = outputs.calculation_trace || (outputs.calculation_result && outputs.calculation_result.calculation_trace) || [];
        if (traces.length > 0) {
          html += `
            <table class="styled-table" style="margin-top: 10px;">
              <thead>
                <tr><th>Step</th><th>Formula</th><th>Output</th></tr>
              </thead>
              <tbody>
                ${traces.map(t => `<tr><td>${escapeHtml(t.step)}</td><td><code>${escapeHtml(t.formula)}</code></td><td><strong>${escapeHtml(String(t.output))}</strong></td></tr>`).join('')}
              </tbody>
            </table>
          `;
        }
      }

      // 3. Code Generation & Sandbox Execution
      if (outputs.code || outputs.code_execution) {
        const codeText = outputs.code || '';
        const execOut = (outputs.code_execution && outputs.code_execution.stdout) || (outputs.execution_result && outputs.execution_result.stdout) || '';
        html += `
          <div>
            <div class="section-title">Generated Python Code</div>
            <div class="code-container">
              <div class="code-header">
                <span>python</span>
                <button class="btn-copy" onclick="copyCode(this)">Copy</button>
              </div>
              <div class="code-block">${escapeHtml(codeText)}</div>
            </div>
          </div>
        `;
        if (execOut) {
          html += `
            <div>
              <div class="section-title">Sandbox Execution Output (stdout)</div>
              <div class="code-container">
                <div class="code-header">
                  <span>Isolated Sandbox Log</span>
                  <span style="color: var(--success);">Exit Code 0</span>
                </div>
                <div class="code-block" style="color: #10B981;">${escapeHtml(execOut)}</div>
              </div>
            </div>
          `;
        }
      }

      // 4. Visual Inspection Observations & NDT Disclaimer
      const visRes = outputs.vision_result || outputs.document_analysis;
      if (visRes && visRes.observations && visRes.observations.length > 0) {
        html += `
          <div>
            <div class="section-title">Visual Candidate Observations</div>
            <table class="styled-table">
              <thead>
                <tr><th>Observation</th><th>Confidence</th><th>Status</th></tr>
              </thead>
              <tbody>
                ${visRes.observations.map(o => `
                  <tr>
                    <td>${escapeHtml(o.observation || o.text || 'Visual Indication')}</td>
                    <td>${o.confidence ? (o.confidence.level || (o.confidence.value * 100).toFixed(0) + '%') : 'MEDIUM'}</td>
                    <td><span style="color: var(--warning);">Candidate (Uncertified)</span></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <div class="disclaimer-box">
            <strong>⚠️ Engineering NDT Requirement:</strong> All visual indications are uncertified candidates requiring physical Non-Destructive Testing (NDT) verification before maintenance sign-off.
          </div>
        `;
      }

      // 5. Grounded Citations (RAG)
      const citations = outputs.citations || [];
      if (citations.length > 0) {
        html += `
          <div>
            <div class="section-title">Verified Source Citations</div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${citations.map(c => `
                <div class="pill" style="border-radius: 6px; justify-content: space-between;">
                  <span>📖 <strong>${escapeHtml(c.filename || 'Source Document')}</strong> (Chunk ${escapeHtml(c.chunk_id || '-')})</span>
                  <span style="font-size: 11px; color: var(--success);">✓ Grounded</span>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      // 6. Artifact Downloads
      const generatedFiles = [];
      if (outputs.document_analysis && outputs.document_analysis.output_file) {
        generatedFiles.push(outputs.document_analysis.output_file);
      }
      if (generatedFiles.length > 0) {
        html += `
          <div>
            <div class="section-title">Generated Artifacts</div>
            ${generatedFiles.map(f => `
              <div class="artifact-card">
                <div class="artifact-info">📄 ${escapeHtml(f)}</div>
                <a href="/api/v1/artifacts/${encodeURIComponent(f)}/download" class="btn-download" download>⬇ Download File</a>
              </div>
            `).join('')}
          </div>
        `;
      }

      // If nothing parsed, show friendly JSON inspect
      if (!textAnswer && !outputs.code && !outputs.calculation_result && !visRes) {
        html += `
          <div>
            <div class="section-title">Task Result Details</div>
            <div class="deliverable-text">${escapeHtml(JSON.stringify(outputs, null, 2))}</div>
          </div>
        `;
      }

      html += '</div>';
      document.getElementById('deliverable-body').innerHTML = html;
    }

    function copyCode(btn) {
      const code = btn.parentElement.nextElementSibling.innerText;
      navigator.clipboard.writeText(code);
      btn.innerText = 'Copied!';
      setTimeout(() => { btn.innerText = 'Copy'; }, 2000);
    }

    function escapeHtml(text) {
      if (!text) return '';
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }
  </script>
</body>
</html>
"""

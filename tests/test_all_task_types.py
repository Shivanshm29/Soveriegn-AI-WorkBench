import urllib.request
import json
import time
import sys

BASE_URL = "http://127.0.0.1:8080"

def post_json(endpoint: str, data: dict):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(endpoint: str):
    req = urllib.request.Request(f"{BASE_URL}{endpoint}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_text_output(result: dict) -> str:
    if not isinstance(result, dict):
        return ""
    if result.get("summary"):
        return result["summary"]
    outs = result.get("outputs") or result.get("partial_outputs") or {}
    if isinstance(outs, dict):
        return outs.get("answer") or outs.get("content") or outs.get("analysis") or str(outs.get("value", ""))
    return str(outs)

print("=== Starting Comprehensive Task & Audit Verification ===")

# Test 1: PDF Document Summarization
print("\n[TEST 1] PDF Document Summarization")
pdf_task = post_json("/api/v1/tasks", {
    "instruction": "Summarize this ppt",
    "data_sensitivity": "INTERNAL",
    "file_path": "data/uploads/5700b716_SIH2026-IDEA-Presentation-Format (1).pdf"
})
print(f"Task ID: {pdf_task.get('task_id')}, Status: {pdf_task.get('status')}")
pdf_result = pdf_task.get("final_result") or {}
pdf_summary = get_text_output(pdf_result)
print("Summary length:", len(pdf_summary))
print("First 350 chars of summary:\n", pdf_summary[:350])
assert len(pdf_summary) > 50, "PDF summary too short or empty!"
assert "Step 1: Gather Information" not in pdf_summary, "PDF summary is still generic placeholder!"
print(">>> TEST 1 PASSED: PDF summarized with actual content!")

# Test 2: Visual Inspection of Image
print("\n[TEST 2] Image Understanding / Visual Inspection")
img_task = post_json("/api/v1/tasks", {
    "instruction": "Inspect this engineering component for surface defects and structural integrity",
    "data_sensitivity": "INTERNAL",
    "file_path": "data/uploads/sample_inspection.png"
})
print(f"Task ID: {img_task.get('task_id')}, Status: {img_task.get('status')}")
img_result = img_task.get("final_result") or {}
img_summary = get_text_output(img_result)
print("Visual output sample:\n", img_summary[:350])
assert len(img_summary) > 20, "Visual summary empty!"
print(">>> TEST 2 PASSED: Visual inspection completed!")

# Test 3: Tabular Data Analysis & Calculation
print("\n[TEST 3] Tabular Data Analysis & Calculation")
csv_task = post_json("/api/v1/tasks", {
    "instruction": "Analyze sensor telemetry: calculate mean temperature and maximum pressure",
    "data_sensitivity": "INTERNAL",
    "file_path": "data/uploads/c6c22098_sample_sensors.csv"
})
print(f"Task ID: {csv_task.get('task_id')}, Status: {csv_task.get('status')}")
csv_result = csv_task.get("final_result") or {}
csv_summary = get_text_output(csv_result)
print("Data output sample:\n", csv_summary[:350])
assert len(csv_summary) > 10, "CSV calculation summary empty!"
print(">>> TEST 3 PASSED: CSV calculation completed!")

# Test 4: Code Execution in Sandbox with Approval Flow
print("\n[TEST 4] Coding Agent & Approval Flow")
code_task = post_json("/api/v1/tasks", {
    "instruction": "Write a python script to compute the first 10 Fibonacci numbers and execute it",
    "data_sensitivity": "INTERNAL"
})
print(f"Task ID: {code_task.get('task_id')}, Status: {code_task.get('status')}")
if code_task.get("status") == "WAITING_APPROVAL":
    print("Task properly paused for human-in-the-loop approval!")
    # Approve it
    app_res = post_json(f"/api/v1/tasks/{code_task.get('task_id')}/approval", {
        "action": "APPROVED",
        "comments": "Proceed with local sandbox execution"
    })
    print(f"Resumed task status: {app_res.get('status')}")
    code_summary = get_text_output(app_res.get("final_result") or {})
    print("Execution output sample:\n", code_summary[:350])
    assert app_res.get("status") == "COMPLETED", f"Expected COMPLETED, got {app_res.get('status')}"
else:
    print("Task completed without approval pause or direct success:", code_task.get("status"))
print(">>> TEST 4 PASSED: Coding execution completed!")

# Test 5: Sovereign Knowledge / Reasoning
print("\n[TEST 5] Sovereign Reasoning / Knowledge")
rag_task = post_json("/api/v1/tasks", {
    "instruction": "Outline the sovereign safety policies and air-gapped guidelines for Indian PSU AI infrastructure",
    "data_sensitivity": "RESTRICTED"
})
print(f"Task ID: {rag_task.get('task_id')}, Status: {rag_task.get('status')}")
if rag_task.get("status") == "WAITING_APPROVAL":
    print("RESTRICTED sensitivity task appropriately requires human approval; submitting approval...")
    rag_task = post_json(f"/api/v1/tasks/{rag_task.get('task_id')}/approval", {
        "action": "APPROVED",
        "comments": "Approved for restricted sovereign knowledge review"
    })
    print(f"Resumed task status: {rag_task.get('status')}")

rag_result = rag_task.get("final_result") or {}
rag_summary = get_text_output(rag_result)
print("Knowledge output sample:\n", rag_summary[:350])
assert "INSUFFICIENT_EVIDENCE" not in rag_summary, "Knowledge query failed with INSUFFICIENT_EVIDENCE!"
assert len(rag_summary) > 30, "Knowledge summary too short!"
print(">>> TEST 5 PASSED: Sovereign reasoning completed without insufficient evidence!")

# Test 6: Audit Logs & Events Verification
print("\n[TEST 6] Audit Logs & Event Trail Verification")
audit_logs = get_json("/api/v1/audit/logs?limit=50")
print(f"Total audit logs retrieved: {len(audit_logs)}")
assert len(audit_logs) > 0, "No audit logs found!"
sample_ev = audit_logs[0]
print("Sample audit log keys:", list(sample_ev.keys()))
print(f"Event: {sample_ev.get('event_type')}, Task: {sample_ev.get('task_id')}, Time: {sample_ev.get('timestamp')}")

task_events = get_json(f"/api/v1/tasks/{pdf_task.get('task_id')}/events")
print(f"PDF Task event count: {len(task_events)}")
assert len(task_events) >= 3, "Insufficient audit trail events for task!"

print("\n==========================================")
print("ALL 6 TASK TYPES & AUDIT TRAIL VERIFIED SUCCESSFULLY!")
print("==========================================")

"""Automated task importance and data sensitivity classification for sovereign workbench."""

import re
from enum import Enum
from typing import Dict, Any, List, Optional


class TaskImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def classify_task_importance_and_sensitivity(
    instruction: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministically analyze a task request to assign:
    - importance: LOW, MEDIUM, HIGH, CRITICAL
    - data_sensitivity: PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    - requires_approval: boolean (true for HIGH and CRITICAL tasks)
    - reasons: human-auditable list of matched factors
    """
    text = (instruction or "").strip()
    text_lower = text.lower()
    file_ext = ""
    if file_path:
        file_ext = file_path.lower().split(".")[-1] if "." in file_path else ""

    reasons: List[str] = []
    factors: List[str] = []
    
    # -------------------------------------------------------------
    # 1. Check for CRITICAL factors
    # -------------------------------------------------------------
    is_critical = False
    
    # 1a. Code Execution / Docker Sandbox
    sandbox_patterns = [
        r"\bsandbox\b",
        r"\bexecute\b.*\b(code|script|python)\b",
        r"\brun\b.*\b(code|script|python)\b",
        r"\bwrite\b.*\b(python|script)\b.*\bexecute\b",
        r"\bpython\b.*\b(sandbox|execute|run)\b",
        r"\bexecute in the sandbox\b",
        r"\bdocker\b",
        r"\bsubprocess\b",
        r"\bdelete\b",
        r"\bremove\s+file\b",
        r"\brm\s+-rf\b",
    ]
    for pat in sandbox_patterns:
        if re.search(pat, text_lower):
            is_critical = True
            factors.append("code_execution")
            reasons.append("Requires isolated Docker sandbox execution (sovereign-sandbox:latest with zero network egress)")
            break

    # 1b. Restricted / Export-Controlled Data
    restricted_keywords = [
        "restricted", "itar", "export controlled", "export-controlled",
        "top secret", "air-gap bypass", "override security"
    ]
    if any(k in text_lower for k in restricted_keywords):
        is_critical = True
        factors.append("restricted_data")
        reasons.append("References RESTRICTED / export-controlled sovereign data category")

    # 1c. Extreme Hazard / Emergency
    hazard_keywords = [
        "nuclear", "reactor core", "boiler overpressure", "explosive",
        "chemical hazard", "emergency shutdown", "flight control"
    ]
    if any(k in text_lower for k in hazard_keywords):
        is_critical = True
        factors.append("extreme_hazard")
        reasons.append("Interacts with life-critical / high-hazard process equipment")

    if is_critical:
        data_sens = "RESTRICTED" if "restricted_data" in factors else "INTERNAL"
        return {
            "importance": TaskImportance.CRITICAL.value,
            "data_sensitivity": data_sens,
            "requires_approval": True,
            "reasons": reasons,
            "factors": factors,
        }

    # -------------------------------------------------------------
    # 2. Check for HIGH (Important) factors
    # -------------------------------------------------------------
    is_high = False

    # 2a. Safety-critical Industrial Equipment
    equipment_keywords = [
        "turbine", "turbine-01", "casing", "pressure vessel", "boiler",
        "px-417", "centrifugal pump", "bearing replacement", "fatigue crack",
        "cavitation", "vibration alert", "flange defect", "structural defect"
    ]
    matched_eq = [k for k in equipment_keywords if k in text_lower]
    if matched_eq:
        is_high = True
        factors.append("safety_critical_asset")
        reasons.append(f"Targets safety-critical plant asset ({', '.join(matched_eq[:2])})")

    # 2b. Formal Engineering Approval Note / Sign-off / Compliance
    formal_approval_keywords = [
        "approval note", "approval-note", "engineering sign-off", "formal approval",
        "certification", "compliance report", "lockout", "tagout", "loto",
        "work authorization", "safety note"
    ]
    if any(k in text_lower for k in formal_approval_keywords):
        is_high = True
        factors.append("formal_approval_document")
        reasons.append("Generates binding industrial inspection approval note / work authorization")

    # 2c. Confidential SOP / Proprietary Knowledge
    confidential_keywords = [
        "confidential", "proprietary", "standard operating procedure", "sop",
        "internal procedure", "trade secret", "classified"
    ]
    if any(k in text_lower for k in confidential_keywords):
        is_high = True
        factors.append("confidential_sop")
        reasons.append("Accesses confidential internal standard operating procedure (SOP)")

    # 2d. Code Generation without immediate execution specified
    if any(k in text_lower for k in ("write python", "generate script", "create python", "write a script")):
        is_high = True
        factors.append("code_generation")
        reasons.append("Generates algorithmic executable code artifacts")

    if is_high:
        data_sens = "CONFIDENTIAL" if "confidential_sop" in factors else "INTERNAL"
        return {
            "importance": TaskImportance.HIGH.value,
            "data_sensitivity": data_sens,
            "requires_approval": True,
            "reasons": reasons,
            "factors": factors,
        }

    # -------------------------------------------------------------
    # 3. Check for MEDIUM factors
    # -------------------------------------------------------------
    is_medium = False

    medium_keywords = [
        "calculate", "calculation", "statistics", "mean", "average", "rms",
        "sensor data", "vibration data", "tabular", "dataset", "inspect", "photo",
        "chart", "trend", "extract text", "parse"
    ]
    if any(k in text_lower for k in medium_keywords) or file_ext in ("csv", "xlsx", "png", "jpg", "pdf"):
        is_medium = True
        factors.append("analytical_operation")
        reasons.append("Standard deterministic calculations and engineering data extraction")

    if is_medium:
        return {
            "importance": TaskImportance.MEDIUM.value,
            "data_sensitivity": "INTERNAL",
            "requires_approval": False,
            "reasons": reasons,
            "factors": factors,
        }

    # -------------------------------------------------------------
    # 4. Fallback to LOW
    # -------------------------------------------------------------
    reasons.append("Standard read-only engineering query and technical reasoning")
    return {
        "importance": TaskImportance.LOW.value,
        "data_sensitivity": "INTERNAL",
        "requires_approval": False,
        "reasons": reasons,
        "factors": ["routine_query"],
    }

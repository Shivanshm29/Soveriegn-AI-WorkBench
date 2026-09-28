"""Deterministic risk assessment engine for sovereign workbench."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.tools.registry import ToolRegistry
from backend.app.security.data_sensitivity import DataSensitivity


class RiskLevel(str, Enum):
    """Deterministic risk classification tiers."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFactor(str, Enum):
    """Granular risk factors evaluated during plan analysis."""
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    EXTERNAL_NETWORK_ACCESS = "external_network_access"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    CODE_EXECUTION = "code_execution"
    SPREADSHEET_MODIFICATION = "spreadsheet_modification"
    DOCUMENT_GENERATION = "document_generation"
    SYSTEM_CONFIGURATION = "system_configuration"
    PRIVILEGED_OPERATION = "privileged_operation"
    HIGH_IMPACT_OUTPUT = "high_impact_output"


class RiskAssessment(BaseModel):
    """Structured, immutable record of deterministic risk assessment."""

    task_id: str
    plan_id: str
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_factors: List[str] = Field(default_factory=list)
    affected_resources: List[str] = Field(default_factory=list)
    affected_tools: List[str] = Field(default_factory=list)
    affected_data: List[str] = Field(default_factory=list)
    reasoning: str
    policy_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert risk assessment to serializable dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        """Instantiate risk assessment from dictionary."""
        return cls.model_validate(data)


class RiskEngine:
    """Evaluates plan steps and context deterministically to calculate risk."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None, policy_config: Optional[Dict[str, Any]] = None):
        self.tool_registry = tool_registry or ToolRegistry()
        self.policy_config = policy_config or {}
        self.thresholds = self.policy_config.get("risk_thresholds", {
            "low_max": 0.25,
            "medium_max": 0.50,
            "high_max": 0.75,
            "critical_min": 0.75,
        })
        self.policy_version = str(self.policy_config.get("policy_version", "1.0.0"))

    def assess_plan(
        self,
        task_id: str,
        plan_id: str,
        plan_steps: List[Any],
        data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Deterministically assess the risk of a proposed plan."""
        metadata = metadata or {}
        risk_factors: List[str] = []
        affected_resources: List[str] = []
        affected_tools: List[str] = []
        affected_data: List[str] = [data_sensitivity.value]
        reason_parts: List[str] = []

        max_tool_score = 0.0
        has_critical_factor = False
        has_high_factor = False

        # 1. Evaluate Data Sensitivity
        if data_sensitivity == DataSensitivity.RESTRICTED:
            risk_factors.append(RiskFactor.SENSITIVE_DATA_ACCESS.value)
            risk_factors.append(RiskFactor.HIGH_IMPACT_OUTPUT.value)
            reason_parts.append("Accessing RESTRICTED classified data")
            has_high_factor = True
            base_data_score = 0.45
        elif data_sensitivity == DataSensitivity.CONFIDENTIAL:
            risk_factors.append(RiskFactor.SENSITIVE_DATA_ACCESS.value)
            reason_parts.append("Accessing CONFIDENTIAL classified data")
            base_data_score = 0.25
        elif data_sensitivity == DataSensitivity.INTERNAL:
            base_data_score = 0.10
        else:
            base_data_score = 0.05

        # 2. Evaluate Tools in Plan
        for step in plan_steps:
            # step can be PlanStep or dict
            step_id = getattr(step, "step_id", None) or (step.get("step_id") if isinstance(step, dict) else "unknown")
            tools = getattr(step, "required_tools", None) or (step.get("required_tools", []) if isinstance(step, dict) else [])
            action = getattr(step, "description", None) or (step.get("description", "") if isinstance(step, dict) else "")

            for tool_id in tools:
                if tool_id not in affected_tools:
                    affected_tools.append(tool_id)

                tool = self.tool_registry.get(tool_id)
                if not tool:
                    # Unknown tool is a privileged / critical risk factor (fails closed)
                    risk_factors.append(RiskFactor.PRIVILEGED_OPERATION.value)
                    reason_parts.append(f"Unknown tool '{tool_id}' requested in step '{step_id}'")
                    has_critical_factor = True
                    max_tool_score = max(max_tool_score, 0.95)
                    continue

                tool_risk = getattr(tool, "risk_level", "LOW")
                if tool_risk == "CRITICAL":
                    has_critical_factor = True
                    max_tool_score = max(max_tool_score, 0.85)
                elif tool_risk == "HIGH":
                    has_high_factor = True
                    max_tool_score = max(max_tool_score, 0.70)
                elif tool_risk == "MEDIUM":
                    max_tool_score = max(max_tool_score, 0.40)
                else:
                    max_tool_score = max(max_tool_score, 0.15)

                # Map tool capabilities to explicit risk factors
                if tool_id == "sandbox_execute":
                    risk_factors.append(RiskFactor.CODE_EXECUTION.value)
                    has_high_factor = True
                    reason_parts.append(f"Code execution tool '{tool_id}' requested in step '{step_id}'")
                elif tool_id == "file_write":
                    risk_factors.append(RiskFactor.FILE_WRITE.value)
                    affected_resources.append("local_filesystem")
                elif tool_id in ("create_xlsx", "python_calculation"):
                    risk_factors.append(RiskFactor.SPREADSHEET_MODIFICATION.value)
                elif tool_id == "create_docx":
                    risk_factors.append(RiskFactor.DOCUMENT_GENERATION.value)

            # Check text descriptions for explicit forbidden or high-risk cues
            action_lower = action.lower()
            if "delete" in action_lower or "remove file" in action_lower:
                risk_factors.append(RiskFactor.FILE_DELETE.value)
                has_high_factor = True
                max_tool_score = max(max_tool_score, 0.75)
                reason_parts.append(f"File deletion action indicated in step '{step_id}'")
            if "network" in action_lower or "http" in action_lower or "curl" in action_lower:
                risk_factors.append(RiskFactor.EXTERNAL_NETWORK_ACCESS.value)
                has_critical_factor = True
                max_tool_score = max(max_tool_score, 0.99)
                reason_parts.append(f"External network access requested in step '{step_id}'")
            if "config" in action_lower or "system" in action_lower:
                risk_factors.append(RiskFactor.SYSTEM_CONFIGURATION.value)

        # 3. Calculate Deterministic Composite Risk Score
        raw_score = base_data_score + (max_tool_score * 0.7)
        risk_score = round(min(1.0, max(0.05, raw_score)), 3)

        # De-duplicate factors
        unique_factors = list(dict.fromkeys(risk_factors))

        # 4. Determine Risk Level from Score & Factors
        low_max = float(self.thresholds.get("low_max", 0.25))
        med_max = float(self.thresholds.get("medium_max", 0.50))
        high_max = float(self.thresholds.get("high_max", 0.75))

        if has_critical_factor or risk_score > high_max:
            risk_level = RiskLevel.CRITICAL
        elif has_high_factor or risk_score > med_max:
            risk_level = RiskLevel.HIGH
        elif risk_score > low_max:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        if not reason_parts:
            reason_parts.append(f"Plan evaluated with {len(plan_steps)} steps and risk score {risk_score}")

        reasoning = "; ".join(reason_parts)

        return RiskAssessment(
            task_id=task_id,
            plan_id=plan_id,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=unique_factors,
            affected_resources=list(dict.fromkeys(affected_resources)),
            affected_tools=affected_tools,
            affected_data=affected_data,
            reasoning=reasoning,
            policy_version=self.policy_version,
        )

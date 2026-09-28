"""Deterministic policy evaluation engine for sovereign workbench."""

import os
import uuid
import yaml
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field

from backend.app.tools.registry import ToolRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.security.risk import RiskAssessment, RiskLevel, RiskFactor, RiskEngine
from backend.app.security.data_sensitivity import DataSensitivity, parse_data_sensitivity


class PolicyOutcome(str, Enum):
    """Deterministic policy determination outcomes."""
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class PolicyDecision(BaseModel):
    """Structured, auditable policy decision object."""

    decision: PolicyOutcome
    reason: str
    risk_level: str
    policy_version: str = "1.0.0"
    matched_rules: List[str] = Field(default_factory=list)
    task_id: str = ""
    plan_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flagged_tools: List[str] = Field(default_factory=list)
    requires_approval: bool = False

    @property
    def status(self) -> str:
        """Backwards-compatible alias for decision status."""
        if self.decision == PolicyOutcome.ALLOW:
            return "allowed"
        elif self.decision == PolicyOutcome.REQUIRE_APPROVAL:
            return "requires_approval"
        else:
            return "blocked"

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary."""
        d = self.model_dump(mode="json")
        d["status"] = self.status
        d["decision"] = self.decision.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyDecision":
        """Instantiate decision from dictionary."""
        return cls.model_validate(data)


class PolicyEngine:
    """Evaluates proposed execution plans against local configuration and sovereignty rules."""

    DEFAULT_POLICY_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "configs",
        "policies.yaml",
    )

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        agent_registry: Optional[AgentRegistry] = None,
        policy_config_path: Optional[str] = None,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.agent_registry = agent_registry or AgentRegistry()
        self.config_path = policy_config_path or self.DEFAULT_POLICY_PATH
        self.config = self._load_policy_config()
        self.policy_version = str(self.config.get("policy_version", "1.0.0"))
        self.risk_engine = RiskEngine(self.tool_registry, self.config)

    def _load_policy_config(self) -> Dict[str, Any]:
        """Load local YAML policy rules. If missing or invalid, fail-closed."""
        if not os.path.exists(self.config_path):
            # Fail closed: returns empty or default restrictive config
            return {"policy_version": "1.0.0-unconfigured", "denied_operations": ["*"]}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data or {}
        except Exception:
            return {"policy_version": "1.0.0-error", "denied_operations": ["*"]}

    def evaluate_plan(
        self,
        plan_steps: List[Any],
        task_id: str = "",
        plan_id: str = "",
        data_sensitivity: Union[str, DataSensitivity] = DataSensitivity.INTERNAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[PolicyDecision, RiskAssessment]:
        """
        Evaluate full plan following strict precedence:
        1. Sovereignty constraints
        2. Hard security restrictions & registry validation (Fail-Closed)
        3. Policy configuration denied operations
        4. Risk assessment & approval requirements
        5. Allow
        """
        task_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
        plan_id = plan_id or f"plan-{uuid.uuid4().hex[:8]}"
        sensitivity = parse_data_sensitivity(data_sensitivity)
        metadata = metadata or {}

        # If policy configuration failed to load, fail closed immediately
        if self.config.get("policy_version") in ("1.0.0-unconfigured", "1.0.0-error"):
            decision = PolicyDecision(
                decision=PolicyOutcome.DENY,
                reason="Policy configuration missing or unreadable; failing closed.",
                risk_level=RiskLevel.CRITICAL.value,
                policy_version=self.policy_version,
                matched_rules=["FAIL_CLOSED_NO_CONFIG"],
                task_id=task_id,
                plan_id=plan_id,
                requires_approval=False,
            )
            assessment = self.risk_engine.assess_plan(task_id, plan_id, plan_steps, sensitivity)
            return decision, assessment

        matched_rules: List[str] = []
        flagged_tools: List[str] = []
        reasons: List[str] = []

        # Perform deterministic risk assessment
        risk_assessment = self.risk_engine.assess_plan(
            task_id=task_id,
            plan_id=plan_id,
            plan_steps=plan_steps,
            data_sensitivity=sensitivity,
            metadata=metadata,
        )

        # ---------------------------------------------------------
        # PRECEDENCE 1: Sovereignty Constraints (Cannot be bypassed)
        # ---------------------------------------------------------
        sovereignty_cfg = self.config.get("sovereignty_restrictions", {})
        if sovereignty_cfg.get("deny_external_network", True):
            if RiskFactor.EXTERNAL_NETWORK_ACCESS.value in risk_assessment.risk_factors:
                return PolicyDecision(
                    decision=PolicyOutcome.DENY,
                    reason="Sovereignty constraint: External network access is strictly prohibited in sovereign air-gap mode.",
                    risk_level=RiskLevel.CRITICAL.value,
                    policy_version=self.policy_version,
                    matched_rules=["SOVEREIGNTY_NO_EXTERNAL_NETWORK"],
                    task_id=task_id,
                    plan_id=plan_id,
                    requires_approval=False,
                ), risk_assessment

        # ---------------------------------------------------------
        # PRECEDENCE 2: Hard Security & Registry Validation (Fail Closed)
        # ---------------------------------------------------------
        for step in plan_steps:
            step_id = step.get("step_id") if isinstance(step, dict) else getattr(step, "step_id", "")
            agent_id = step.get("agent_id") if isinstance(step, dict) else getattr(step, "agent_id", "")
            tools = step.get("required_tools", []) if isinstance(step, dict) else getattr(step, "required_tools", [])

            # Validate agent exists in authoritative AgentRegistry
            if agent_id and not self.agent_registry.get(agent_id):
                return PolicyDecision(
                    decision=PolicyOutcome.DENY,
                    reason=f"Unknown agent '{agent_id}' requested in step '{step_id}'; failing closed.",
                    risk_level=RiskLevel.CRITICAL.value,
                    policy_version=self.policy_version,
                    matched_rules=["FAIL_CLOSED_UNKNOWN_AGENT"],
                    task_id=task_id,
                    plan_id=plan_id,
                    requires_approval=False,
                ), risk_assessment

            # Validate tools exist in authoritative ToolRegistry
            for tool_id in tools:
                tool = self.tool_registry.get(tool_id)
                if not tool:
                    return PolicyDecision(
                        decision=PolicyOutcome.DENY,
                        reason=f"Unknown tool '{tool_id}' requested in step '{step_id}'; failing closed.",
                        risk_level=RiskLevel.CRITICAL.value,
                        policy_version=self.policy_version,
                        matched_rules=["FAIL_CLOSED_UNKNOWN_TOOL"],
                        task_id=task_id,
                        plan_id=plan_id,
                        requires_approval=False,
                    ), risk_assessment

        # ---------------------------------------------------------
        # PRECEDENCE 3: Denied Operations from Config
        # ---------------------------------------------------------
        denied_ops = self.config.get("denied_operations", [])
        for factor in risk_assessment.risk_factors:
            if factor in denied_ops:
                return PolicyDecision(
                    decision=PolicyOutcome.DENY,
                    reason=f"Policy rule denies operation '{factor}' unconditionally.",
                    risk_level=RiskLevel.CRITICAL.value,
                    policy_version=self.policy_version,
                    matched_rules=[f"DENIED_OP_{factor.upper()}"],
                    task_id=task_id,
                    plan_id=plan_id,
                    requires_approval=False,
                ), risk_assessment

        # ---------------------------------------------------------
        # PRECEDENCE 4: Approval Requirements
        # ---------------------------------------------------------
        needs_approval = False
        approval_cfg = self.config.get("approval_requirements", {})

        # Check risk level thresholds requiring approval
        if risk_assessment.risk_level.value in approval_cfg.get("risk_levels", ["HIGH", "CRITICAL"]):
            needs_approval = True
            matched_rules.append("APPROVAL_REQUIRED_RISK_LEVEL")
            reasons.append(f"Risk level is {risk_assessment.risk_level.value}")

        # Check data sensitivity
        if sensitivity.value in approval_cfg.get("data_sensitivities", ["RESTRICTED"]):
            needs_approval = True
            matched_rules.append("APPROVAL_REQUIRED_DATA_SENSITIVITY")
            reasons.append(f"Data sensitivity is {sensitivity.value}")

        # Check tool specific approval rules
        req_tools = approval_cfg.get("tools", ["sandbox_execute"])
        for tool_id in risk_assessment.affected_tools:
            tool = self.tool_registry.get(tool_id)
            if tool and (tool.requires_approval or tool_id in req_tools):
                needs_approval = True
                flagged_tools.append(tool_id)
                matched_rules.append(f"APPROVAL_REQUIRED_TOOL_{tool_id.upper()}")
                reasons.append(f"Tool '{tool_id}' requires explicit approval")

        # Check factors
        req_factors = approval_cfg.get("factors", [])
        for f in risk_assessment.risk_factors:
            if f in req_factors:
                needs_approval = True
                matched_rules.append(f"APPROVAL_REQUIRED_FACTOR_{f.upper()}")
                reasons.append(f"Risk factor '{f}' requires approval")

        if needs_approval:
            flagged_unique = list(dict.fromkeys(flagged_tools))
            return PolicyDecision(
                decision=PolicyOutcome.REQUIRE_APPROVAL,
                reason="; ".join(reasons) if reasons else "Human authorization required by policy",
                risk_level=risk_assessment.risk_level.value,
                policy_version=self.policy_version,
                matched_rules=list(dict.fromkeys(matched_rules)),
                task_id=task_id,
                plan_id=plan_id,
                flagged_tools=flagged_unique,
                requires_approval=True,
            ), risk_assessment

        # ---------------------------------------------------------
        # PRECEDENCE 5: ALLOW
        # ---------------------------------------------------------
        return PolicyDecision(
            decision=PolicyOutcome.ALLOW,
            reason="Plan operations strictly conform to sovereign policy rules.",
            risk_level=risk_assessment.risk_level.value,
            policy_version=self.policy_version,
            matched_rules=["POLICY_ALLOW"],
            task_id=task_id,
            plan_id=plan_id,
            flagged_tools=[],
            requires_approval=False,
        ), risk_assessment

    def evaluate_step(self, step: Any) -> PolicyDecision:
        """Evaluate a single step for backwards compatibility with PolicyEvaluator interface."""
        decision, _ = self.evaluate_plan([step])
        return decision

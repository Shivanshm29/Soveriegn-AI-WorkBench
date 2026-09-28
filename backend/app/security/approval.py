"""Human authorization and approval model for sovereign workbench."""

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field

from backend.app.security.risk import RiskAssessment


class ApprovalStatus(str, Enum):
    """Lifecycle states for human approval requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


def compute_plan_hash(plan_steps: List[Any]) -> str:
    """Generate deterministic SHA-256 fingerprint of plan to detect tampering/modifications."""
    canonical_repr = []
    for step in plan_steps:
        if isinstance(step, dict):
            step_id = step.get("step_id", "")
            action = step.get("description", "")
            tools = sorted(step.get("required_tools", []))
            agent = step.get("agent_id", "")
            deps = sorted(step.get("dependencies", []))
        else:
            step_id = getattr(step, "step_id", "")
            action = getattr(step, "description", "")
            tools = sorted(getattr(step, "required_tools", []))
            agent = getattr(step, "agent_id", "")
            deps = sorted(getattr(step, "dependencies", []))
        canonical_repr.append({
            "step_id": step_id,
            "description": action,
            "required_tools": tools,
            "agent_id": agent,
            "dependencies": deps,
        })
    encoded = json.dumps(canonical_repr, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ApprovalRequest(BaseModel):
    """Formal request requiring human authorization before proceeding."""

    approval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    plan_id: str
    requested_by: str = "policy_engine"
    risk_level: str
    action_summary: str
    affected_resources: List[str] = Field(default_factory=list)
    affected_tools: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    policy_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    status: ApprovalStatus = ApprovalStatus.PENDING
    plan_hash: str = ""
    authorization_scope: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check whether the approval request has exceeded its expiration window."""
        now = current_time or datetime.now(timezone.utc)
        return now > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert approval request to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Instantiate approval request from dictionary."""
        return cls.model_validate(data)


class ApprovalDecision(BaseModel):
    """Immutable human approval or rejection determination."""

    approval_id: str
    decision: Literal["APPROVED", "REJECTED"]
    approver: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    authorization_scope: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalDecision":
        """Instantiate decision from dictionary."""
        return cls.model_validate(data)


class ApprovalManager:
    """Manages creation, immutability, scope verification, and expiration of approvals."""

    @staticmethod
    def create_request(
        task_id: str,
        plan_id: str,
        risk_assessment: RiskAssessment,
        plan_steps: List[Any],
        reasons: Optional[List[str]] = None,
        timeout_seconds: int = 3600,
        policy_version: str = "1.0.0",
    ) -> ApprovalRequest:
        """Create a new pending ApprovalRequest bound to a specific plan hash."""
        reasons = reasons or [risk_assessment.reasoning]
        plan_hash = compute_plan_hash(plan_steps)

        # Build scope mapping tools and step IDs
        scope_steps = []
        for s in plan_steps:
            s_id = s.get("step_id") if isinstance(s, dict) else getattr(s, "step_id", "")
            scope_steps.append(s_id)

        scope = {
            "task_id": task_id,
            "plan_id": plan_id,
            "plan_hash": plan_hash,
            "authorized_steps": scope_steps,
            "authorized_tools": list(risk_assessment.affected_tools),
        }

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout_seconds)

        action_summary = (
            f"Human approval required for plan '{plan_id}' with {len(plan_steps)} steps "
            f"(Risk: {risk_assessment.risk_level.value}, Tools: {risk_assessment.affected_tools})"
        )

        return ApprovalRequest(
            task_id=task_id,
            plan_id=plan_id,
            risk_level=risk_assessment.risk_level.value,
            action_summary=action_summary,
            affected_resources=risk_assessment.affected_resources,
            affected_tools=risk_assessment.affected_tools,
            reasons=reasons,
            policy_version=policy_version,
            created_at=now,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING,
            plan_hash=plan_hash,
            authorization_scope=scope,
        )

    @staticmethod
    def validate_approval(
        request: ApprovalRequest,
        decision: ApprovalDecision,
        current_plan_steps: List[Any],
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, str, ApprovalStatus]:
        """
        Validate decision against request, ensuring non-expiration and scope integrity.
        Returns: (is_valid, reason, resulting_status)
        """
        now = current_time or datetime.now(timezone.utc)

        # 1. Verify ID match
        if decision.approval_id != request.approval_id:
            return False, f"Approval ID mismatch: decision '{decision.approval_id}' != request '{request.approval_id}'", ApprovalStatus.REJECTED

        # 2. Check Expiration
        if request.is_expired(now):
            return False, f"Approval request '{request.approval_id}' has expired at {request.expires_at.isoformat()}", ApprovalStatus.EXPIRED

        # 3. Check Approver identity
        if not decision.approver or not decision.approver.strip():
            return False, "Approver identity must be specified and non-empty", ApprovalStatus.REJECTED

        # 4. Check Plan Hash (detect material plan change)
        current_hash = compute_plan_hash(current_plan_steps)
        if current_hash != request.plan_hash:
            return False, "Plan was modified after approval was requested. Re-approval required.", ApprovalStatus.CANCELLED

        # 5. Check Decision status
        if decision.decision == "REJECTED":
            return False, f"Approval rejected by {decision.approver}: {decision.reason}", ApprovalStatus.REJECTED

        if decision.decision == "APPROVED":
            return True, f"Approval granted by {decision.approver}", ApprovalStatus.APPROVED

        return False, f"Unknown decision value: {decision.decision}", ApprovalStatus.REJECTED

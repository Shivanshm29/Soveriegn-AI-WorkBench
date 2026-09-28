"""Generic verification of plan execution completeness and results."""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    """Outcome of generic plan execution verification."""

    is_verified: bool
    completed_steps: int
    total_steps: int
    missing_outputs: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return self.model_dump(mode="json")


class PlanVerifier:
    """Verifies that all required plan steps completed successfully with required outputs."""

    @staticmethod
    def verify(
        plan: List[Dict[str, Any]],
        execution_steps: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
    ) -> VerificationResult:
        """Verify plan completion."""
        total_steps = len(plan)
        if total_steps == 0:
            return VerificationResult(
                is_verified=False,
                completed_steps=0,
                total_steps=0,
                errors=["Cannot verify empty plan."],
            )

        completed_count = 0
        missing_outputs: List[str] = []
        errors: List[str] = []

        # Map step executions by step_id
        step_exec_map = {s["step_id"]: s for s in execution_steps if "step_id" in s}

        for planned in plan:
            sid = planned["step_id"]
            step_record = step_exec_map.get(sid)

            if not step_record:
                errors.append(f"Step '{sid}' was planned but never executed.")
                continue

            if step_record.get("status") == "COMPLETED":
                completed_count += 1
                # Check expected output key if specified
                expected_key = planned.get("expected_output")
                if expected_key and expected_key not in step_record.get("outputs", {}):
                    # Check if outputs is not empty
                    if not step_record.get("outputs"):
                        missing_outputs.append(f"Step '{sid}' completed without outputs.")
            elif step_record.get("status") == "FAILED":
                errors.append(f"Step '{sid}' failed: {step_record.get('error', 'unknown error')}")
            elif step_record.get("status") == "SKIPPED":
                completed_count += 1

        is_verified = (completed_count == total_steps) and (len(errors) == 0) and (len(missing_outputs) == 0)

        return VerificationResult(
            is_verified=is_verified,
            completed_steps=completed_count,
            total_steps=total_steps,
            missing_outputs=missing_outputs,
            errors=errors,
            details={"step_count": total_steps, "completed_count": completed_count},
        )

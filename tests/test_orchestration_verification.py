"""Test J: Verification Node and Completeness Checking."""

import pytest
from backend.app.orchestration.verification import PlanVerifier, VerificationResult


def test_verification_passes_when_all_steps_completed():
    """Verify verification succeeds when all steps have completed records."""
    plan = [
        {"step_id": "s1", "expected_output": "data"},
        {"step_id": "s2", "expected_output": "report"},
    ]
    execution_steps = [
        {"step_id": "s1", "status": "COMPLETED", "outputs": {"data": "ok"}},
        {"step_id": "s2", "status": "COMPLETED", "outputs": {"report": "final"}},
    ]
    observations = [
        {"step_id": "s1", "outcome": "SUCCESS"},
        {"step_id": "s2", "outcome": "SUCCESS"},
    ]
    res = PlanVerifier.verify(plan, execution_steps, observations)
    assert res.is_verified is True
    assert res.completed_steps == 2


def test_verification_fails_when_step_missing():
    """Verify verification fails when a planned step was not executed."""
    plan = [
        {"step_id": "s1"},
        {"step_id": "s2"},
    ]
    execution_steps = [
        {"step_id": "s1", "status": "COMPLETED", "outputs": {"val": 1}},
    ]
    res = PlanVerifier.verify(plan, execution_steps, [])
    assert res.is_verified is False
    assert any("never executed" in e for e in res.errors)


def test_verification_fails_when_step_failed():
    """Verify verification fails when an execution step has FAILED status."""
    plan = [{"step_id": "s1"}]
    execution_steps = [
        {"step_id": "s1", "status": "FAILED", "error": "Execution crashed"},
    ]
    res = PlanVerifier.verify(plan, execution_steps, [])
    assert res.is_verified is False
    assert any("failed" in e.lower() for e in res.errors)

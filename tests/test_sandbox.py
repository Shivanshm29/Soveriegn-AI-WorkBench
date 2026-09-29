"""Unit and safety tests for local network-isolated sandbox execution."""

import os
import pytest
from backend.app.sandbox import (
    SandboxManager,
    get_sandbox_manager,
    CodeExecutionRequest,
    SandboxConfig,
    LocalProcessSandbox,
    PathTraversalError,
    SandboxSecurityViolationError,
    CodeExecutionVerifier,
)
from tests.fixtures.phase_9_fixtures import (
    SAMPLE_CODE_NORMAL,
    SAMPLE_CODE_NETWORK_ATTEMPT,
    SAMPLE_CODE_TIMEOUT,
)


def test_sandbox_creation_and_workspace():
    """Verify local sandbox creates isolated workspace directory."""
    sbx = LocalProcessSandbox()
    assert os.path.exists(sbx.workspace_path)
    assert sbx.sandbox_id.startswith("sbx_")
    sbx.cleanup()
    assert not os.path.exists(sbx.workspace_path)


def test_sandbox_successful_execution():
    """Verify valid code executes successfully and returns expected stdout."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(
        code=SAMPLE_CODE_NORMAL,
        expected_output_patterns=[r"COUNT: 5", r"MEAN: 13.40"],
    )
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "SUCCESS"
    assert res.exit_code == 0
    assert "COUNT: 5" in res.stdout
    assert "SUM: 67.00" in res.stdout
    assert res.verification_status is not None
    assert res.verification_status.is_verified is True


def test_sandbox_network_isolation_blocked():
    """Verify external network access is blocked inside sandbox execution."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(code=SAMPLE_CODE_NETWORK_ATTEMPT)
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "SUCCESS"
    # User code caught the network blocked error
    assert "NETWORK_BLOCKED_CAUGHT: NETWORK ACCESS BLOCKED" in res.stdout
    assert res.network_blocked is True


def test_sandbox_direct_network_attempt_fails():
    """Verify unhandled network request fails with blocked status."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(
        code="import urllib.request\nurllib.request.urlopen('https://example.com', timeout=3)"
    )
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "BLOCKED"
    assert "NETWORK ACCESS BLOCKED" in res.stderr
    assert res.network_blocked is True


def test_sandbox_path_traversal_blocked():
    """Verify attempts to write or read outside sandbox workspace raise PathTraversalError."""
    sbx = LocalProcessSandbox()
    with pytest.raises(PathTraversalError):
        sbx.write_file("../../outside.txt", "payload")

    with pytest.raises(PathTraversalError):
        sbx.read_file("..\\..\\secret.txt")

    sbx.cleanup()


def test_sandbox_restricted_file_access_blocked():
    """Verify access to sensitive credentials (.env, id_rsa, .ssh) is strictly denied."""
    sbx = LocalProcessSandbox()
    with pytest.raises(SandboxSecurityViolationError):
        sbx.write_file(".env", "SECRET=123")

    with pytest.raises(SandboxSecurityViolationError):
        sbx.write_file("id_rsa", "PRIVATE KEY")

    sbx.cleanup()


def test_sandbox_file_io_in_workspace():
    """Verify sandbox input files can be written and read within workspace boundaries."""
    sbx = LocalProcessSandbox()
    written_path = sbx.write_file("data/input.txt", "sovereign data")
    assert os.path.exists(written_path)
    content = sbx.read_file("data/input.txt")
    assert content == "sovereign data"
    sbx.cleanup()


def test_sandbox_timeout_enforcement():
    """Verify long-running processes are terminated when exceeding timeout."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(
        code=SAMPLE_CODE_TIMEOUT,
        config=SandboxConfig(timeout_seconds=2),
    )
    res = mgr.execute_code(req, force_local=True)
    assert res.status == "TIMEOUT"
    assert "timeout" in (res.error or "").lower()
    assert res.verification_status is not None
    assert res.verification_status.is_verified is False


def test_sandbox_output_size_limit():
    """Verify sandbox output is truncated if exceeding max_output_bytes."""
    mgr = get_sandbox_manager()
    req = CodeExecutionRequest(
        code="print('A' * 2000)",
        config=SandboxConfig(max_output_bytes=500),
    )
    res = mgr.execute_code(req, force_local=True)
    assert len(res.stdout) <= 600
    assert "[OUTPUT TRUNCATED" in res.stdout


def test_code_execution_verifier_detects_failure():
    """Verify CodeExecutionVerifier correctly identifies non-zero returncodes and missing patterns."""
    req = CodeExecutionRequest(
        code="print('Hello')",
        expected_output_patterns=["ExpectedNonExistentPattern"],
    )
    res = get_sandbox_manager().execute_code(req, force_local=True)
    assert res.verification_status is not None
    assert res.verification_status.is_verified is False
    assert any("Missing expected output pattern" in r for r in res.verification_status.failure_reasons)

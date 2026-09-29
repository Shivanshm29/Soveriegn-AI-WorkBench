"""Local process-based isolated sandbox provider with network blocking and safe workspace containment."""

import os
import sys
import shutil
import tempfile
import time
import uuid
import subprocess
from typing import Dict, List, Optional, Union, Set
from pathlib import Path

from backend.app.sandbox.base import BaseSandbox
from backend.app.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    ResourceUsage,
    SandboxConfig,
)
from backend.app.sandbox.errors import (
    PathTraversalError,
    SandboxSecurityViolationError,
    SandboxTimeoutError,
    ResourceLimitExceededError,
    NetworkAccessBlockedError,
)
from backend.app.sandbox.verifier import CodeExecutionVerifier


RESTRICTED_FILENAMES = {
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "known_hosts",
    "authorized_keys",
    ".git",
    ".bash_history",
    "credentials",
    "secrets.json",
}

NETWORK_ISOLATION_PRELUDE = """# Sovereign Sandbox Network Isolation Harness
import sys
import socket

def _network_blocked_error(*args, **kwargs):
    raise RuntimeError("NETWORK ACCESS BLOCKED: Sandbox network is disabled")

# 1. Patch low-level socket operations
socket.socket.connect = _network_blocked_error
socket.socket.connect_ex = _network_blocked_error
socket.create_connection = _network_blocked_error
socket.getaddrinfo = _network_blocked_error
socket.gethostbyname = _network_blocked_error
socket.gethostbyname_ex = _network_blocked_error

# 2. Patch standard library HTTP / URL clients
try:
    import urllib.request
    urllib.request.urlopen = _network_blocked_error
except Exception:
    pass

try:
    import http.client
    http.client.HTTPConnection.connect = _network_blocked_error
    http.client.HTTPSConnection.connect = _network_blocked_error
except Exception:
    pass

# 3. Patch third-party network libraries if present
try:
    import requests
    requests.Session.send = _network_blocked_error
except Exception:
    pass

try:
    import httpx
    httpx.Client.send = _network_blocked_error
    httpx.AsyncClient.send = _network_blocked_error
except Exception:
    pass

# 4. Remove network environment proxies
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    if _k in sys.modules.get("os", {}).environ:
        del sys.modules["os"].environ[_k]
"""


class LocalProcessSandbox(BaseSandbox):
    """Secure local process sandbox enforcing strict directory containment and network denial."""

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        base_dir: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ):
        self._sandbox_id = sandbox_id or f"sbx_{uuid.uuid4().hex[:12]}"
        self._config = config or SandboxConfig()

        if base_dir:
            self._workspace_path = os.path.abspath(os.path.join(base_dir, self._sandbox_id))
            os.makedirs(self._workspace_path, exist_ok=True)
            self._is_temp = False
        else:
            self._temp_dir = tempfile.TemporaryDirectory(prefix=self._config.temp_dir_prefix)
            self._workspace_path = os.path.abspath(self._temp_dir.name)
            self._is_temp = True

    @property
    def sandbox_id(self) -> str:
        return self._sandbox_id

    @property
    def workspace_path(self) -> str:
        return self._workspace_path

    def _validate_safe_path(self, relative_path: str) -> str:
        """Validate and resolve relative path, strictly preventing traversal or restricted access."""
        norm_rel = os.path.normpath(relative_path).lstrip("\\/")

        # Block parent directory traversal
        if ".." in norm_rel.split(os.sep) or ".." in norm_rel.split("/"):
            raise PathTraversalError(f"Path traversal blocked: '{relative_path}' attempts to escape workspace.")

        # Block absolute paths
        if os.path.isabs(relative_path) or (len(relative_path) > 1 and relative_path[1] == ":"):
            raise PathTraversalError(f"Absolute path access blocked: '{relative_path}'. Only workspace paths allowed.")

        # Check restricted filenames
        basename = os.path.basename(norm_rel).lower()
        if basename in RESTRICTED_FILENAMES or any(r in norm_rel.lower() for r in [".ssh", ".env"]):
            raise SandboxSecurityViolationError(
                f"Security violation: access to sensitive credential/configuration file '{relative_path}' is denied."
            )

        full_path = os.path.abspath(os.path.join(self._workspace_path, norm_rel))
        # Ensure resolved path is inside workspace
        if not full_path.startswith(self._workspace_path):
            raise PathTraversalError(f"Resolved path '{full_path}' escapes workspace '{self._workspace_path}'.")

        return full_path

    def write_file(self, relative_path: str, content: Union[str, bytes]) -> str:
        """Safely write an input file into the sandbox workspace."""
        full_path = self._validate_safe_path(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(full_path, mode, encoding=encoding) as f:
            f.write(content)
        return full_path

    def read_file(self, relative_path: str) -> str:
        """Safely read an output file from the sandbox workspace."""
        full_path = self._validate_safe_path(relative_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found in sandbox: '{relative_path}'")
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _snapshot_files(self) -> Set[str]:
        """Record all existing files inside workspace."""
        files = set()
        for root, _, filenames in os.walk(self._workspace_path):
            for fname in filenames:
                rel = os.path.relpath(os.path.join(root, fname), self._workspace_path)
                files.add(rel)
        return files

    def execute(self, request: CodeExecutionRequest) -> CodeExecutionResult:
        """Execute Python code in local process with network denial harness and resource limits."""
        start_time = time.perf_counter()

        # 1. Populate input files
        for rel_name, content in request.input_files.items():
            self.write_file(rel_name, content)

        initial_files = self._snapshot_files()

        # 2. Write script harness with network isolation
        harness_filename = "_sandbox_exec.py"
        full_code = f"{NETWORK_ISOLATION_PRELUDE}\n# User Code:\n{request.code}\n"
        harness_path = os.path.join(self._workspace_path, harness_filename)
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(full_code)

        # 3. Environment sanitization: isolate from host secrets and browser data
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        # 4. Run subprocess
        cmd = [sys.executable, harness_filename] + request.command_args
        status = "SUCCESS"
        exit_code = None
        stdout = ""
        stderr = ""
        error_msg = None
        timed_out = False

        try:
            proc = subprocess.run(
                cmd,
                cwd=self._workspace_path,
                env=clean_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=request.config.timeout_seconds,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr

            if exit_code != 0:
                if "NETWORK ACCESS BLOCKED" in stderr or "NETWORK ACCESS BLOCKED" in stdout:
                    status = "BLOCKED"
                    error_msg = "Execution failed due to blocked network access attempt."
                else:
                    status = "FAILED"
                    error_msg = f"Process exited with non-zero status {exit_code}."

        except subprocess.TimeoutExpired as te:
            timed_out = True
            status = "TIMEOUT"
            stdout = te.stdout or ""
            stderr = te.stderr or ""
            error_msg = f"Execution exceeded timeout limit of {request.config.timeout_seconds}s."
            exit_code = None
        except Exception as e:
            status = "ERROR"
            error_msg = f"Subprocess runner failed: {e}"

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Enforce max output bytes limit
        if len(stdout) > request.config.max_output_bytes:
            stdout = stdout[: request.config.max_output_bytes] + "\n[OUTPUT TRUNCATED: Exceeded max_output_bytes]"
        if len(stderr) > request.config.max_output_bytes:
            stderr = stderr[: request.config.max_output_bytes] + "\n[OUTPUT TRUNCATED: Exceeded max_output_bytes]"

        # 5. Detect created/modified files
        post_files = self._snapshot_files()
        created_files = sorted(list((post_files - initial_files) - {harness_filename}))

        # Copy created artifacts to central artifacts cache
        if created_files and os.path.exists(self._workspace_path):
            artifacts_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache", "artifacts")
            )
            os.makedirs(artifacts_dir, exist_ok=True)
            for cf in created_files:
                src = os.path.join(self._workspace_path, cf)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(artifacts_dir, cf))

        result = CodeExecutionResult(
            task_id=request.task_id,
            sandbox_id=self._sandbox_id,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=round(duration_ms, 2),
            resource_usage=ResourceUsage(
                duration_ms=round(duration_ms, 2),
                output_bytes=len(stdout) + len(stderr),
            ),
            network_blocked=True,
            files_created=created_files,
            files_modified=[],
            error=error_msg,
        )

        # 6. Verification
        verification = CodeExecutionVerifier.verify(request, result, self._workspace_path)
        result.verification_status = verification
        if not verification.is_verified and result.status == "SUCCESS":
            result.status = "FAILED"
            result.error = "; ".join(verification.failure_reasons)

        if self._config.cleanup_after_run:
            self.cleanup()

        return result

    def cleanup(self) -> None:
        """Securely remove temporary workspace files."""
        try:
            if hasattr(self, "_temp_dir") and self._temp_dir:
                self._temp_dir.cleanup()
            elif os.path.exists(self._workspace_path):
                shutil.rmtree(self._workspace_path, ignore_errors=True)
        except Exception:
            pass

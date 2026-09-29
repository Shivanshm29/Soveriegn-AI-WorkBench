"""Docker container-based execution sandbox enforcing kernel-level network and resource isolation."""

import os
import shutil
import tempfile
import time
import uuid
import subprocess
from typing import Dict, List, Optional, Union, Set

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
    SandboxExecutionError,
)
from backend.app.sandbox.verifier import CodeExecutionVerifier


class DockerSandbox(BaseSandbox):
    """Docker-based execution sandbox enforcing --network none and container cgroup limits."""

    IMAGE_NAME = "python:3.11-slim"

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        base_dir: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ):
        self._sandbox_id = sandbox_id or f"sbx_docker_{uuid.uuid4().hex[:12]}"
        self._config = config or SandboxConfig()

        if base_dir:
            self._workspace_path = os.path.abspath(os.path.join(base_dir, self._sandbox_id))
            os.makedirs(self._workspace_path, exist_ok=True)
            self._is_temp = False
        else:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="docker_sandbox_")
            self._workspace_path = os.path.abspath(self._temp_dir.name)
            self._is_temp = True

    @property
    def sandbox_id(self) -> str:
        return self._sandbox_id

    @property
    def workspace_path(self) -> str:
        return self._workspace_path

    @staticmethod
    def is_docker_available() -> bool:
        """Check if Docker CLI and daemon are reachable."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    def write_file(self, relative_path: str, content: Union[str, bytes]) -> str:
        """Safely write an input file into the sandbox workspace."""
        norm_rel = os.path.normpath(relative_path).lstrip("\\/")
        if ".." in norm_rel.split(os.sep) or ".." in norm_rel.split("/"):
            raise PathTraversalError(f"Path traversal blocked: '{relative_path}'")
        if os.path.isabs(relative_path) or (len(relative_path) > 1 and relative_path[1] == ":"):
            raise PathTraversalError(f"Absolute path blocked: '{relative_path}'")

        full_path = os.path.abspath(os.path.join(self._workspace_path, norm_rel))
        if not full_path.startswith(self._workspace_path):
            raise PathTraversalError(f"Escaped workspace: '{relative_path}'")

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(full_path, mode, encoding=encoding) as f:
            f.write(content)
        return full_path

    def read_file(self, relative_path: str) -> str:
        """Safely read an output file from the sandbox workspace."""
        full_path = os.path.abspath(os.path.join(self._workspace_path, os.path.normpath(relative_path)))
        if not full_path.startswith(self._workspace_path):
            raise PathTraversalError(f"Escaped workspace: '{relative_path}'")
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found in sandbox: '{relative_path}'")
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def execute(self, request: CodeExecutionRequest) -> CodeExecutionResult:
        """Execute code in Docker container with network disabled and cgroup resource caps."""
        if not self.is_docker_available():
            raise SandboxExecutionError("Docker daemon is not available or not running.")

        start_time = time.perf_counter()

        # 1. Populate input files
        for rel_name, content in request.input_files.items():
            self.write_file(rel_name, content)

        # 2. Write script file
        script_name = "main.py"
        self.write_file(script_name, request.code)

        # 3. Assemble docker command with strict isolation
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            f"--memory={request.config.max_memory_mb}m",
            "--cpus=1.0",
            "--pids-limit=64",
            "-v", f"{self._workspace_path}:/workspace:rw",
            "-w", "/workspace",
            self.IMAGE_NAME,
            "python", script_name,
        ] + request.command_args

        status = "SUCCESS"
        exit_code = None
        stdout = ""
        stderr = ""
        error_msg = None

        try:
            proc = subprocess.run(
                docker_cmd,
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
                status = "FAILED"
                error_msg = f"Docker container exited with code {exit_code}."
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
            error_msg = f"Container execution timed out after {request.config.timeout_seconds}s."
        except Exception as e:
            status = "ERROR"
            error_msg = f"Docker execution error: {e}"

        duration_ms = (time.perf_counter() - start_time) * 1000.0

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
            error=error_msg,
        )

        verification = CodeExecutionVerifier.verify(request, result, self._workspace_path)
        result.verification_status = verification
        if not verification.is_verified and result.status == "SUCCESS":
            result.status = "FAILED"
            result.error = "; ".join(verification.failure_reasons)

        if self._config.cleanup_after_run:
            self.cleanup()

        return result

    def cleanup(self) -> None:
        """Clean up workspace directory."""
        try:
            if hasattr(self, "_temp_dir") and self._temp_dir:
                self._temp_dir.cleanup()
            elif os.path.exists(self._workspace_path):
                shutil.rmtree(self._workspace_path, ignore_errors=True)
        except Exception:
            pass

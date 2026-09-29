"""Pydantic schemas for local network-isolated sandbox execution."""

import uuid
from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Runtime limits and configuration for an isolated sandbox instance."""

    timeout_seconds: int = 15
    max_memory_mb: int = 512
    max_output_bytes: int = 100_000
    network_enabled: bool = False
    isolate_filesystem: bool = True
    temp_dir_prefix: str = "sovereign_sandbox_"
    cleanup_after_run: bool = True


class ResourceUsage(BaseModel):
    """Execution telemetry and resource consumption."""

    cpu_time_ms: float = 0.0
    memory_peak_mb: float = 0.0
    duration_ms: float = 0.0
    output_bytes: int = 0


class VerificationStatus(BaseModel):
    """Deterministic verification results for sandbox execution."""

    is_verified: bool
    checks: Dict[str, bool] = Field(default_factory=dict)
    failure_reasons: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class CodeExecutionRequest(BaseModel):
    """Request contract for executing code inside an isolated sandbox."""

    code: str
    language: str = "python"
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_files: Dict[str, Union[str, bytes]] = Field(default_factory=dict)
    command_args: List[str] = Field(default_factory=list)
    config: SandboxConfig = Field(default_factory=SandboxConfig)
    expected_files: List[str] = Field(default_factory=list)
    expected_output_patterns: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CodeExecutionResult(BaseModel):
    """Authoritative structured outcome of code execution inside the sandbox."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    sandbox_id: str
    status: Literal["SUCCESS", "FAILED", "TIMEOUT", "BLOCKED", "ERROR"]
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    network_blocked: bool = True
    files_created: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    verification_status: Optional[VerificationStatus] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert execution result to dictionary."""
        return self.model_dump(mode="json")

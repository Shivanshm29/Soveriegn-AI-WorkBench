"""Tool contracts and handlers for sandbox execution."""

from typing import Dict, Any, Optional, List, Union
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry
from backend.app.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    SandboxConfig,
)
from backend.app.sandbox.manager import get_sandbox_manager


def run_sandbox_execution(
    code: str,
    task_id: str = "default_task",
    input_files: Optional[Dict[str, Union[str, bytes]]] = None,
    timeout_seconds: int = 15,
    max_memory_mb: int = 512,
    expected_files: Optional[List[str]] = None,
    expected_output_patterns: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute code in the local isolated sandbox and return structured result dictionary."""
    config = SandboxConfig(
        timeout_seconds=timeout_seconds,
        max_memory_mb=max_memory_mb,
    )
    request = CodeExecutionRequest(
        code=code,
        task_id=task_id,
        input_files=input_files or {},
        config=config,
        expected_files=expected_files or [],
        expected_output_patterns=expected_output_patterns or [],
        metadata=metadata or {},
    )
    manager = get_sandbox_manager()
    result: CodeExecutionResult = manager.execute_code(request)
    return result.to_dict()


def register_sandbox_tools(registry: ToolRegistry) -> None:
    """Ensure sandbox tools are registered in the ToolRegistry with authoritative HIGH risk level."""
    sandbox_tool = ToolContract(
        tool_id="sandbox_execute",
        name="Isolated Sandbox Runner",
        description="Executes arbitrary generated code inside a strictly isolated, unprivileged local sandbox.",
        capabilities=["code_execution", "sandbox_testing"],
        risk_level="HIGH",
        requires_approval=True,
        enabled=True,
    )
    registry.register(sandbox_tool, overwrite=True)

"""Sandbox manager coordinating container and process sandbox instances."""

import logging
from typing import Dict, Optional

from backend.app.sandbox.base import BaseSandbox
from backend.app.sandbox.docker_sandbox import DockerSandbox
from backend.app.sandbox.local_sandbox import LocalProcessSandbox
from backend.app.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    SandboxConfig,
)

logger = logging.getLogger("app.sandbox.manager")


class SandboxManager:
    """Coordinates sandbox provider selection, lifecycle management, and execution."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        default_config: Optional[SandboxConfig] = None,
        prefer_docker: bool = False,
    ):
        self._base_dir = base_dir
        self._default_config = default_config or SandboxConfig()
        self._prefer_docker = prefer_docker
        self._active_sandboxes: Dict[str, BaseSandbox] = {}

    def create_sandbox(
        self,
        sandbox_id: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
        force_local: bool = False,
    ) -> BaseSandbox:
        """Create a new sandbox provider, selecting Docker if available and preferred."""
        effective_config = config or self._default_config

        if not force_local and self._prefer_docker and DockerSandbox.is_docker_available():
            logger.info("Instantiating DockerSandbox provider (--network none).")
            sbx = DockerSandbox(
                sandbox_id=sandbox_id,
                base_dir=self._base_dir,
                config=effective_config,
            )
        else:
            logger.info("Instantiating LocalProcessSandbox provider with network isolation harness.")
            sbx = LocalProcessSandbox(
                sandbox_id=sandbox_id,
                base_dir=self._base_dir,
                config=effective_config,
            )

        self._active_sandboxes[sbx.sandbox_id] = sbx
        return sbx

    def execute_code(
        self,
        request: CodeExecutionRequest,
        force_local: bool = False,
    ) -> CodeExecutionResult:
        """Create a dedicated sandbox, execute the code, and return structured outcome."""
        sandbox = self.create_sandbox(config=request.config, force_local=force_local)
        try:
            return sandbox.execute(request)
        finally:
            if sandbox.sandbox_id in self._active_sandboxes:
                del self._active_sandboxes[sandbox.sandbox_id]

    def cleanup_all(self) -> None:
        """Clean up any tracked active sandboxes."""
        for sbx in list(self._active_sandboxes.values()):
            sbx.cleanup()
        self._active_sandboxes.clear()


# Global singleton manager
_default_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """Retrieve or initialize the global SandboxManager."""
    global _default_sandbox_manager
    if _default_sandbox_manager is None:
        _default_sandbox_manager = SandboxManager()
    return _default_sandbox_manager

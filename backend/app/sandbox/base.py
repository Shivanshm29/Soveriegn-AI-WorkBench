"""Abstract base contract for local sandbox implementations."""

import abc
from typing import Dict, Any, Optional
from backend.app.sandbox.schemas import CodeExecutionRequest, CodeExecutionResult


class BaseSandbox(abc.ABC):
    """Abstract interface defining required sandbox lifecycle and execution behaviors."""

    @property
    @abc.abstractmethod
    def sandbox_id(self) -> str:
        """Unique identifier of the sandbox instance."""
        pass

    @property
    @abc.abstractmethod
    def workspace_path(self) -> str:
        """Absolute path to the isolated sandbox workspace directory."""
        pass

    @abc.abstractmethod
    def execute(self, request: CodeExecutionRequest) -> CodeExecutionResult:
        """Execute the requested code inside the sandbox with strict isolation."""
        pass

    @abc.abstractmethod
    def write_file(self, relative_path: str, content: str | bytes) -> str:
        """Safely write an input file into the sandbox workspace, blocking traversal."""
        pass

    @abc.abstractmethod
    def read_file(self, relative_path: str) -> str:
        """Safely read an output file from the sandbox workspace, blocking traversal."""
        pass

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Tear down and securely erase temporary workspace resources."""
        pass

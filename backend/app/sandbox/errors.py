"""Structured exceptions for sandbox execution and isolation."""


class SandboxError(Exception):
    """Base exception for all sandbox-related errors."""
    pass


class NetworkAccessBlockedError(SandboxError):
    """Raised when executed code attempts to access the external network."""
    pass


class SandboxTimeoutError(SandboxError):
    """Raised when code execution exceeds the allocated timeout."""
    pass


class ResourceLimitExceededError(SandboxError):
    """Raised when memory, CPU, or output limits are exceeded."""
    pass


class PathTraversalError(SandboxError):
    """Raised when file operations attempt to traverse outside the sandbox workspace."""
    pass


class SandboxExecutionError(SandboxError):
    """Raised when the sandbox runner fails to execute the process."""
    pass


class SandboxSecurityViolationError(SandboxError):
    """Raised when restricted files or system resources are accessed."""
    pass

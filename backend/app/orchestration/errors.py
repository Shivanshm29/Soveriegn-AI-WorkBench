"""Orchestration structured exceptions."""


class OrchestrationError(Exception):
    """Base exception for all orchestration errors."""
    pass


class TaskUnderstandingError(OrchestrationError):
    """Raised when the UNDERSTAND node fails to produce a valid task specification."""
    pass


class RoutingError(OrchestrationError):
    """Raised when the ROUTE node fails to resolve appropriate agents or models."""
    pass


class InvalidPlanError(OrchestrationError):
    """Raised when a generated plan fails structural or semantic validation."""
    pass


class UnknownAgentError(OrchestrationError):
    """Raised when a plan references an agent not in the AgentRegistry."""
    pass


class UnknownToolError(OrchestrationError):
    """Raised when a plan references a tool not in the ToolRegistry."""
    pass


class PolicyBlockedError(OrchestrationError):
    """Raised when the POLICY checkpoint blocks a step or plan."""
    pass


class StepExecutionError(OrchestrationError):
    """Raised when a step execution fails fatally."""
    pass


class AgentNotImplementedError(OrchestrationError):
    """Raised or returned when an agent capability is not yet implemented (truthful execution)."""
    pass


class MaxRetriesExceededError(OrchestrationError):
    """Raised when retry count exceeds MAX_RETRIES configuration."""
    pass


class MaxStepsExceededError(OrchestrationError):
    """Raised when execution step count exceeds MAX_AGENT_STEPS configuration."""
    pass


class VerificationError(OrchestrationError):
    """Raised when VERIFY detects incomplete or inconsistent outputs."""
    pass

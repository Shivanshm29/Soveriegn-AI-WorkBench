"""Structured exceptions for the Model Runtime layer."""


class ModelRuntimeError(Exception):
    """Base exception for all model runtime errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ModelUnavailableError(ModelRuntimeError):
    """Raised when the local model inference server is unreachable or offline."""
    pass


class ModelTimeoutError(ModelRuntimeError):
    """Raised when a model request or health check times out."""
    pass


class ModelNotFoundError(ModelRuntimeError):
    """Raised when a requested model is not found/installed on the runtime server."""
    pass


class ModelConfigurationError(ModelRuntimeError):
    """Raised when runtime configuration is invalid or violates sovereign policy."""
    pass


class ModelResponseError(ModelRuntimeError):
    """Raised when the runtime server returns an unparseable or invalid response."""
    pass


class ModelCapabilityError(ModelRuntimeError):
    """Raised when a requested capability, modality, or structured format is unsupported."""
    pass

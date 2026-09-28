"""ModelRuntime protocol and abstract interface."""

from abc import ABC, abstractmethod
from typing import List
from backend.app.models.schemas import ModelRequest, ModelResponse
from backend.app.models.health import RuntimeHealth


class ModelRuntime(ABC):
    """Abstract interface for local model execution runtimes."""

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Execute inference on the local model server and return structured response."""
        pass

    def chat(self, request: ModelRequest) -> ModelResponse:
        """Execute inference on the local model server (convenience alias for generate)."""
        return self.generate(request)


    @abstractmethod
    def health_check(self) -> RuntimeHealth:
        """Check runtime health and return structured status."""
        pass

    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return the capabilities supported by this runtime adapter."""
        pass

    @abstractmethod
    def model_available(self, model_name: str) -> bool:
        """Check if a specific model is installed and ready for requests."""
        pass

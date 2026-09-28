"""Model lifecycle abstraction for load, unload, availability, and health."""

from abc import ABC, abstractmethod
from typing import Optional
from backend.app.models.health import RuntimeHealth


class ModelLifecycleManager(ABC):
    """Abstract interface for managing model lifecycles in local runtime environments."""

    @abstractmethod
    def model_available(self, model_name: str) -> bool:
        """Determine whether a model is currently loaded or available for inference."""
        pass

    @abstractmethod
    def load(self, model_name: str) -> bool:
        """Request loading of a model into local runtime memory."""
        pass

    @abstractmethod
    def unload(self, model_name: str) -> bool:
        """Request unloading of a model to free system resources."""
        pass

    @abstractmethod
    def health_check(self) -> RuntimeHealth:
        """Perform health check on the underlying model server."""
        pass


class SimpleModelLifecycleManager(ModelLifecycleManager):
    """Lightweight lifecycle manager delegating to the active runtime adapter."""

    def __init__(self, runtime):
        self.runtime = runtime

    def model_available(self, model_name: str) -> bool:
        return self.runtime.model_available(model_name)

    def load(self, model_name: str) -> bool:
        # In a persistent local server like vLLM, models are managed by the server process
        return self.model_available(model_name)

    def unload(self, model_name: str) -> bool:
        # Placeholder for future dynamic server model management
        return True

    def health_check(self) -> RuntimeHealth:
        return self.runtime.health_check()

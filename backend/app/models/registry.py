"""Model Registry for loading and resolving local model configurations."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from backend.app.schemas.models import (
    ModelDefinition,
    ModelProfileConfig,
    ModelSelection,
)
from backend.app.config.settings import Settings, get_settings


class ModelRegistry:
    """Registry managing model profiles and candidate models."""

    def __init__(self, configs_dir: Optional[str] = None, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if configs_dir:
            self.configs_dir = Path(configs_dir)
        else:
            self.configs_dir = Path(self.settings.CONFIGS_DIR)

        self._profiles: Dict[str, ModelProfileConfig] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load small and high model profile YAML files."""
        small_yaml_path = self.configs_dir / "models.small.yaml"
        high_yaml_path = self.configs_dir / "models.high.yaml"

        if small_yaml_path.exists():
            with open(small_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self._profiles["small"] = ModelProfileConfig(**data)

        if high_yaml_path.exists():
            with open(high_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self._profiles["high"] = ModelProfileConfig(**data)

    @property
    def active_profile_name(self) -> str:
        """Return 'high' if USE_HIGH_LEVEL_MODELS is True, else 'small'."""
        return "high" if self.settings.USE_HIGH_LEVEL_MODELS else "small"

    def get_active_profile(self) -> ModelProfileConfig:
        """Obtain the currently active model profile."""
        profile_name = self.active_profile_name
        if profile_name not in self._profiles:
            raise KeyError(f"Active model profile '{profile_name}' is not loaded.")
        return self._profiles[profile_name]

    def get_profile(self, name: str) -> Optional[ModelProfileConfig]:
        """Obtain a specific profile by name."""
        return self._profiles.get(name)

    def list_active_models(self) -> List[ModelDefinition]:
        """List all enabled models in the active profile."""
        active_prof = self.get_active_profile()
        return [m for m in active_prof.models.values() if m.enabled]

    def get_model_definition(self, slot_or_id: str) -> Optional[ModelDefinition]:
        """Retrieve model definition by slot key (e.g. general_reasoning) or id (e.g. qwen3-small)."""
        active_prof = self.get_active_profile()
        # Direct key lookup
        if slot_or_id in active_prof.models:
            return active_prof.models[slot_or_id]
        # Search by id
        for model in active_prof.models.values():
            if model.id == slot_or_id:
                return model
        return None

    def resolve_model_name(self, slot_or_id: str) -> str:
        """Resolve the runtime model_name string (e.g., Qwen/Qwen3-4B) for a given slot or id."""
        model_def = self.get_model_definition(slot_or_id)
        if not model_def:
            raise KeyError(f"No model found for '{slot_or_id}' in active profile '{self.active_profile_name}'")
        return model_def.model_name

    def find_candidate_models(
        self,
        capabilities: Optional[List[str]] = None,
        modalities: Optional[List[str]] = None,
    ) -> List[ModelDefinition]:
        """Find candidate models in active profile meeting capability and modality constraints."""
        candidates: List[ModelDefinition] = []
        for model in self.list_active_models():
            if capabilities:
                if not all(c in model.capabilities for c in capabilities):
                    continue
            if modalities:
                if not all(m in model.input_modalities for m in modalities):
                    continue
            candidates.append(model)
        return candidates

    def resolve(
        self,
        capabilities: Optional[List[str]] = None,
        modalities: Optional[List[str]] = None,
        slot_hint: Optional[str] = None,
    ) -> ModelSelection:
        """Basic resolution returning ModelSelection with decision reasons."""
        if slot_hint:
            model = self.get_model_definition(slot_hint)
            if model:
                return ModelSelection(
                    selected_model_id=model.id,
                    selected_model_name=model.model_name,
                    active_profile=self.active_profile_name,
                    capabilities=model.capabilities,
                    reason=[f"Resolved via slot hint '{slot_hint}'", f"Active profile: {self.active_profile_name}"],
                )

        candidates = self.find_candidate_models(capabilities, modalities)
        if not candidates:
            # Fallback to general reasoning if available
            general = self.get_model_definition("general_reasoning")
            if general:
                return ModelSelection(
                    selected_model_id=general.id,
                    selected_model_name=general.model_name,
                    active_profile=self.active_profile_name,
                    capabilities=general.capabilities,
                    reason=["Fallback to active general reasoning model"],
                )
            raise RuntimeError(f"No models found matching capabilities {capabilities} in profile '{self.active_profile_name}'")

        selected = candidates[0]
        return ModelSelection(
            selected_model_id=selected.id,
            selected_model_name=selected.model_name,
            active_profile=self.active_profile_name,
            capabilities=selected.capabilities,
            reason=[
                f"Candidate matched capabilities: {capabilities}",
                f"Active profile: {self.active_profile_name}",
            ],
        )

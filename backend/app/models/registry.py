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


class DuplicateModelError(Exception):
    """Raised when attempting to register a model with an ID that already exists."""
    pass


class UnknownModelError(Exception):
    """Raised when a requested model is not found in the registry."""
    pass


class InvalidRegistryDefinitionError(Exception):
    """Raised when a model or entity definition has missing or invalid required fields."""
    pass


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

    def register(
        self,
        model: ModelDefinition,
        profile: Optional[str] = None,
        overwrite: bool = False,
    ) -> None:
        """Register a new model definition in the target profile (defaults to active profile)."""
        if not model.id or not model.model_name:
            raise InvalidRegistryDefinitionError("Model definition must have valid 'id' and 'model_name'.")

        target_prof_name = profile or self.active_profile_name
        if target_prof_name not in self._profiles:
            # Create profile on the fly if registering into a new profile
            self._profiles[target_prof_name] = ModelProfileConfig(
                profile=target_prof_name if target_prof_name in ("small", "high") else "small",
                description=f"Dynamically registered profile {target_prof_name}",
                models={},
            )

        prof = self._profiles[target_prof_name]
        # Check duplicate by id or slot key
        slot_to_overwrite = None
        for existing_slot, existing_model in prof.models.items():
            if existing_model.id == model.id:
                if not overwrite:
                    raise DuplicateModelError(f"Model ID '{model.id}' already exists in profile '{target_prof_name}'.")
                slot_to_overwrite = existing_slot
                break

        slot_key = slot_to_overwrite or model.id.replace("-", "_")
        prof.models[slot_key] = model

    def unregister(self, model_id: str, profile: Optional[str] = None) -> None:
        """Unregister a model from target profile."""
        target_prof_name = profile or self.active_profile_name
        if target_prof_name not in self._profiles:
            raise UnknownModelError(f"Profile '{target_prof_name}' not found.")

        prof = self._profiles[target_prof_name]
        slot_to_remove = None
        for slot, model in prof.models.items():
            if model.id == model_id:
                slot_to_remove = slot
                break

        if slot_to_remove:
            del prof.models[slot_to_remove]
        else:
            raise UnknownModelError(f"Model '{model_id}' not found in profile '{target_prof_name}'.")

    def get(self, model_id_or_slot: str, profile: Optional[str] = None) -> Optional[ModelDefinition]:
        """Retrieve model definition by id or slot key in specified or active profile."""
        target_prof_name = profile or self.active_profile_name
        if target_prof_name not in self._profiles:
            return None

        prof = self._profiles[target_prof_name]
        if model_id_or_slot in prof.models:
            return prof.models[model_id_or_slot]

        for model in prof.models.values():
            if model.id == model_id_or_slot or model.model_name == model_id_or_slot:
                return model
        return None

    def get_or_raise(self, model_id_or_slot: str, profile: Optional[str] = None) -> ModelDefinition:
        """Retrieve model definition by id or slot key, raising UnknownModelError if missing."""
        model = self.get(model_id_or_slot, profile=profile)
        if not model:
            target_prof = profile or self.active_profile_name
            raise UnknownModelError(f"Model '{model_id_or_slot}' not found in profile '{target_prof}'.")
        return model


    def exists(self, model_id_or_slot: str, profile: Optional[str] = None) -> bool:
        """Check if a model exists in specified or active profile."""
        return self.get(model_id_or_slot, profile=profile) is not None

    def list(self, profile: Optional[str] = None) -> List[ModelDefinition]:
        """List all models in the specified or active profile."""
        target_prof_name = profile or self.active_profile_name
        if target_prof_name not in self._profiles:
            return []
        return list(self._profiles[target_prof_name].models.values())

    def list_active_models(self) -> List[ModelDefinition]:
        """List all enabled models in the active profile."""
        active_prof = self.get_active_profile()
        return [m for m in active_prof.models.values() if m.enabled]

    def get_model_definition(self, slot_or_id: str) -> Optional[ModelDefinition]:
        """Retrieve model definition in active profile."""
        return self.get(slot_or_id)

    def resolve_model_name(self, slot_or_id: str) -> str:
        """Resolve the runtime model_name string (e.g., Qwen/Qwen3-4B) for a given slot or id."""
        model_def = self.get_model_definition(slot_or_id)
        if not model_def:
            raise KeyError(f"No model found for '{slot_or_id}' in active profile '{self.active_profile_name}'")
        return model_def.model_name

    def find_by_capability(self, capability: str, profile: Optional[str] = None) -> List[ModelDefinition]:
        """Find models possessing a specific capability."""
        models = self.list(profile=profile)
        return [m for m in models if capability in m.capabilities and m.enabled]

    def find_by_modality(self, modality: str, profile: Optional[str] = None) -> List[ModelDefinition]:
        """Find models supporting a specific input modality."""
        models = self.list(profile=profile)
        return [m for m in models if modality in m.input_modalities and m.enabled]

    def find_by_profile(self, profile: str) -> List[ModelDefinition]:
        """Find all models registered under a profile."""
        return self.list(profile=profile)

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

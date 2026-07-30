"""Model Registry - Unified model lifecycle management.

Manages models through Development → Testing → Staging → Production → Archived stages.
Each model has multiple versions with full traceability between experiment, metadata, and artifacts.

Usage::

    registry = ModelRegistry()
    entry = registry.register("alpha_model", "v4", metadata=meta)
    registry.promote("alpha_model", "v4", ModelStage.PRODUCTION)
    prod = registry.get_production("alpha_model")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from services.ml.metadata import ModelMetadata, ModelStage


@dataclass
class ModelVersion:
    """A single version of a registered model."""

    version: str
    stage: ModelStage = ModelStage.DEVELOPMENT
    metadata: Optional[ModelMetadata] = None
    experiment_id: str = ""
    artifact_ids: List[str] = field(default_factory=list)
    registered_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    promoted_at: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "stage": self.stage.value,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "experiment_id": self.experiment_id,
            "artifact_ids": list(self.artifact_ids),
            "registered_at": self.registered_at,
            "promoted_at": self.promoted_at,
            "metrics": dict(self.metrics),
        }


@dataclass
class RegistryEntry:
    """Entry in the model registry for a named model."""

    model_name: str
    versions: List[ModelVersion] = field(default_factory=list)
    latest_version: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "model_name": self.model_name,
            "versions": [v.to_dict() for v in self.versions],
            "latest_version": self.latest_version,
            "created_at": self.created_at,
            "description": self.description,
            "tags": dict(self.tags),
        }


class ModelRegistry:
    """Central registry for all ML models.

    Manages the full model lifecycle:
        Development → Testing → Staging → Production → Archived
    """

    STAGE_ORDER = {
        ModelStage.DEVELOPMENT: 0,
        ModelStage.TESTING: 1,
        ModelStage.STAGING: 2,
        ModelStage.PRODUCTION: 3,
        ModelStage.ARCHIVED: 4,
    }

    def __init__(self) -> None:
        self._entries: Dict[str, RegistryEntry] = {}
        self._promotion_history: List[Dict[str, Any]] = []

    # ---- Registration ----

    def register(
        self,
        model_name: str,
        version: str,
        metadata: Optional[ModelMetadata] = None,
        experiment_id: str = "",
        artifact_ids: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> RegistryEntry:
        """Register a new model version.

        Args:
            model_name: Unique model name.
            version: Version string (e.g. "v4").
            metadata: Associated model metadata.
            experiment_id: Parent experiment ID.
            artifact_ids: Associated artifact IDs.
            metrics: Model performance metrics.

        Returns:
            The updated RegistryEntry.

        Raises:
            ValueError: If version already exists for this model.
        """
        if self._find_version(model_name, version) is not None:
            raise ValueError(f"Version '{version}' already exists for model '{model_name}'")

        mv = ModelVersion(
            version=version,
            stage=ModelStage.DEVELOPMENT,
            metadata=metadata,
            experiment_id=experiment_id,
            artifact_ids=list(artifact_ids or []),
            metrics=dict(metrics or {}),
        )

        if model_name not in self._entries:
            self._entries[model_name] = RegistryEntry(model_name=model_name)
        entry = self._entries[model_name]
        entry.versions.append(mv)
        entry.versions.sort(key=lambda v: (v.registered_at, v.version), reverse=True)
        entry.latest_version = entry.versions[0].version
        return entry

    def get(self, model_name: str) -> Optional[RegistryEntry]:
        """Get a registry entry by model name."""
        return self._entries.get(model_name)

    def get_version(self, model_name: str, version: str) -> Optional[ModelVersion]:
        """Get a specific version of a model."""
        return self._find_version(model_name, version)

    def list_models(self) -> List[RegistryEntry]:
        """List all registered models."""
        return list(self._entries.values())

    # ---- Promotion ----

    def promote(self, model_name: str, version: str, target_stage: ModelStage) -> bool:
        """Promote a model version to a new stage.

        Follows stage order rules: stages can only move forward,
        and must satisfy minimum previous stage requirements.

        For PRODUCTION promotion: any existing PRODUCTION version
        of the same model is auto-archived.
        """
        mv = self._find_version(model_name, version)
        if mv is None:
            raise ValueError(f"Model '{model_name}' version '{version}' not found")

        current_order = self.STAGE_ORDER.get(mv.stage, -1)
        target_order = self.STAGE_ORDER.get(target_stage, -1)

        if target_order <= current_order:
            raise ValueError(
                f"Cannot demote from {mv.stage.value} to {target_stage.value}. "
                f"Stages must only move forward."
            )

        # Auto-archive existing production version
        if target_stage == ModelStage.PRODUCTION:
            for ver in self._entries.get(model_name, RegistryEntry(model_name)).versions:
                if ver.stage == ModelStage.PRODUCTION and ver.version != version:
                    ver.stage = ModelStage.ARCHIVED

        mv.stage = target_stage
        mv.promoted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if mv.metadata:
            mv.metadata.stage = target_stage

        self._promotion_history.append({
            "model_name": model_name,
            "version": version,
            "from_stage": list(self.STAGE_ORDER.keys())[current_order].value,
            "to_stage": target_stage.value,
            "promoted_at": mv.promoted_at,
        })
        return True

    def demote(self, model_name: str, version: str, target_stage: ModelStage) -> bool:
        """Demote a model version to an earlier stage. Used for rollback."""
        mv = self._find_version(model_name, version)
        if mv is None:
            raise ValueError(f"Model '{model_name}' version '{version}' not found")
        mv.stage = target_stage
        if mv.metadata:
            mv.metadata.stage = target_stage
        return True

    def archive(self, model_name: str, version: str) -> bool:
        """Archive a model version."""
        return self.promote(model_name, version, ModelStage.ARCHIVED)

    def get_production(self, model_name: str) -> Optional[ModelVersion]:
        """Get the production version of a model."""
        entry = self._entries.get(model_name)
        if not entry:
            return None
        for mv in entry.versions:
            if mv.stage == ModelStage.PRODUCTION:
                return mv
        return None

    def get_latest(self, model_name: str) -> Optional[ModelVersion]:
        """Get the latest version of a model by registration time."""
        entry = self._entries.get(model_name)
        if not entry or not entry.versions:
            return None
        return entry.versions[0]

    def list_by_stage(self, stage: ModelStage) -> List[ModelVersion]:
        """List all model versions at a given stage."""
        result = []
        for entry in self._entries.values():
            for mv in entry.versions:
                if mv.stage == stage:
                    result.append(mv)
        return result

    # ---- History ----

    def get_promotion_history(self) -> List[Dict[str, Any]]:
        """Get the full promotion history."""
        return list(self._promotion_history)

    def count(self) -> int:
        """Total number of registered models."""
        return len(self._entries)

    def version_count(self) -> int:
        """Total number of model versions across all models."""
        return sum(len(e.versions) for e in self._entries.values())

    # ---- Internal ----

    def _find_version(self, model_name: str, version: str) -> Optional[ModelVersion]:
        """Find a model version by name and version string."""
        entry = self._entries.get(model_name)
        if not entry:
            return None
        for mv in entry.versions:
            if mv.version == version:
                return mv
        return None

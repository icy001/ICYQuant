"""Model metadata management.

Maintains model information including framework, dataset, author,
creation time, and lineage for full traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import uuid


class ModelFramework(str, Enum):
    """Supported ML frameworks."""

    LIGHTGBM = "LightGBM"
    XGBOOST = "XGBoost"
    CATBOOST = "CatBoost"
    PYTORCH = "PyTorch"
    TENSORFLOW = "TensorFlow"
    SCIKIT_LEARN = "ScikitLearn"
    TRANSFORMER = "Transformer"
    CUSTOM = "Custom"


class ModelStage(str, Enum):
    """Model lifecycle stages."""

    DEVELOPMENT = "Development"
    TESTING = "Testing"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass
class ModelMetadata:
    """Metadata for a registered model.

    Attributes:
        model_name: Unique model name (e.g. "alpha_model").
        version: Version string (e.g. "v4").
        author: Creator of the model.
        framework: ML framework used.
        created_at: ISO 8601 creation timestamp.
        dataset: Training dataset identifier.
        experiment_id: Parent experiment ID.
        features: List of feature names used.
        target: Target variable name.
        hyperparameters: Model hyperparameters dict.
        metrics: Training/evaluation metrics dict.
        git_commit: Git commit hash at training time.
        description: Human-readable description.
        tags: Arbitrary key-value tags.
        lineage: Upstream dependencies (data, features, parent models).
        stage: Current lifecycle stage.
        updated_at: ISO 8601 last update timestamp.
    """

    model_name: str
    version: str
    author: str = "unknown"
    framework: ModelFramework = ModelFramework.LIGHTGBM
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    dataset: str = ""
    experiment_id: str = ""
    features: List[str] = field(default_factory=list)
    target: str = ""
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    git_commit: str = ""
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    stage: ModelStage = ModelStage.DEVELOPMENT
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadata_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "metadata_id": self.metadata_id,
            "model_name": self.model_name,
            "version": self.version,
            "author": self.author,
            "framework": self.framework.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dataset": self.dataset,
            "experiment_id": self.experiment_id,
            "features": list(self.features),
            "target": self.target,
            "hyperparameters": dict(self.hyperparameters),
            "metrics": dict(self.metrics),
            "git_commit": self.git_commit,
            "description": self.description,
            "tags": dict(self.tags),
            "lineage": dict(self.lineage),
            "stage": self.stage.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelMetadata:
        """Deserialize from dictionary."""
        meta = cls(
            model_name=str(data.get("model_name", "")),
            version=str(data.get("version", "")),
            author=str(data.get("author", "unknown")),
        )
        if "framework" in data:
            raw = data["framework"]
            if isinstance(raw, ModelFramework):
                meta.framework = raw
            else:
                meta.framework = ModelFramework(str(raw))
        if "stage" in data:
            raw = data["stage"]
            if isinstance(raw, ModelStage):
                meta.stage = raw
            else:
                meta.stage = ModelStage(str(raw))
        if "created_at" in data:
            meta.created_at = str(data["created_at"])
        if "updated_at" in data:
            meta.updated_at = str(data["updated_at"])
        if "dataset" in data:
            meta.dataset = str(data["dataset"])
        if "experiment_id" in data:
            meta.experiment_id = str(data["experiment_id"])
        if "features" in data:
            meta.features = list(data["features"])  # type: ignore[arg-type]
        if "target" in data:
            meta.target = str(data["target"])
        if "hyperparameters" in data:
            meta.hyperparameters = dict(data["hyperparameters"])  # type: ignore[arg-type]
        if "metrics" in data:
            meta.metrics = dict(data["metrics"])  # type: ignore[arg-type]
        if "git_commit" in data:
            meta.git_commit = str(data["git_commit"])
        if "description" in data:
            meta.description = str(data["description"])
        if "tags" in data:
            meta.tags = dict(data["tags"])  # type: ignore[arg-type]
        if "lineage" in data:
            meta.lineage = dict(data["lineage"])  # type: ignore[arg-type]
        if "metadata_id" in data:
            meta.metadata_id = str(data["metadata_id"])
        return meta


class MetadataManager:
    """Manages model metadata across the entire ML lifecycle.

    Provides CRUD operations for ModelMetadata, including search
    by model name, version, framework, and stage.

    Usage::

        manager = MetadataManager()
        meta = ModelMetadata(model_name="alpha_model", version="v4", framework=ModelFramework.LIGHTGBM)
        manager.save(meta)
        results = manager.list_by_model("alpha_model")
    """

    def __init__(self) -> None:
        self._store: Dict[str, ModelMetadata] = {}
        # Secondary index: model_name -> [metadata_id]
        self._model_index: Dict[str, List[str]] = {}

    # ---- CRUD ----

    def save(self, metadata: ModelMetadata) -> ModelMetadata:
        """Save or update model metadata.

        If a metadata entry with the same model_name + version exists,
        it will be updated.
        """
        existing = self._find_by_name_version(metadata.model_name, metadata.version)
        if existing:
            existing_id = existing.metadata_id
            metadata.metadata_id = existing_id
            metadata.created_at = existing.created_at
            metadata.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._store[existing_id] = metadata
        else:
            self._store[metadata.metadata_id] = metadata
            if metadata.model_name not in self._model_index:
                self._model_index[metadata.model_name] = []
            self._model_index[metadata.model_name].append(metadata.metadata_id)
        return metadata

    def get(self, metadata_id: str) -> Optional[ModelMetadata]:
        """Retrieve metadata by ID."""
        return self._store.get(metadata_id)

    def get_by_name_version(self, model_name: str, version: str) -> Optional[ModelMetadata]:
        """Retrieve metadata by model name and version."""
        return self._find_by_name_version(model_name, version)

    def delete(self, metadata_id: str) -> bool:
        """Delete metadata by ID. Returns True if deleted."""
        meta = self._store.pop(metadata_id, None)
        if meta and meta.model_name in self._model_index:
            idx = self._model_index[meta.model_name]
            if metadata_id in idx:
                idx.remove(metadata_id)
            return True
        return False

    # ---- Queries ----

    def list_by_model(self, model_name: str) -> List[ModelMetadata]:
        """List all versions of a model, newest first."""
        ids = self._model_index.get(model_name, [])
        metas = [self._store[mid] for mid in ids if mid in self._store]
        metas.sort(key=lambda m: (m.created_at, m.version), reverse=True)
        return metas

    def list_all(self) -> List[ModelMetadata]:
        """List all metadata entries."""
        return list(self._store.values())

    def list_by_stage(self, stage: ModelStage) -> List[ModelMetadata]:
        """List all models at a given stage."""
        return [m for m in self._store.values() if m.stage == stage]

    def list_by_framework(self, framework: ModelFramework) -> List[ModelMetadata]:
        """List all models using a given framework."""
        return [m for m in self._store.values() if m.framework == framework]

    def update_stage(self, model_name: str, version: str, stage: ModelStage) -> Optional[ModelMetadata]:
        """Update the lifecycle stage of a model version."""
        meta = self._find_by_name_version(model_name, version)
        if meta:
            meta.stage = stage
            meta.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return meta

    def get_latest_version(self, model_name: str) -> Optional[ModelMetadata]:
        """Get the latest version of a model by creation time."""
        versions = self.list_by_model(model_name)
        return versions[0] if versions else None

    def get_production_model(self, model_name: str) -> Optional[ModelMetadata]:
        """Get the production version of a model."""
        versions = self.list_by_model(model_name)
        for meta in versions:
            if meta.stage == ModelStage.PRODUCTION:
                return meta
        return None

    def count(self) -> int:
        """Return total number of metadata entries."""
        return len(self._store)

    # ---- Internal ----

    def _find_by_name_version(self, model_name: str, version: str) -> Optional[ModelMetadata]:
        """Find metadata by model name and version."""
        ids = self._model_index.get(model_name, [])
        for mid in ids:
            meta = self._store.get(mid)
            if meta and meta.version == version:
                return meta
        return None

"""Model Registry — unified model management for the research platform.

Commit 11 Part 1.5: Central registry for all research models including
alpha models, ML models, AI models, and risk models.

Architecture::

    Model → Version → Artifact → Deployment

Model types:
    - Alpha Model (factor-based prediction)
    - ML Model (gradient boosting, neural networks, etc.)
    - AI Model (LLM-based, agent-based)
    - Risk Model (VaR, CVaR, factor risk)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelRegistryState(str, Enum):
    """Model registry lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class ModelType(str, Enum):
    """Types of models managed by the registry."""

    ALPHA = "alpha"
    ML = "ml"
    AI = "ai"
    RISK = "risk"
    CUSTOM = "custom"


class ModelStatus(str, Enum):
    """Model lifecycle status."""

    DRAFT = "draft"
    TRAINING = "training"
    VALIDATING = "validating"
    READY = "ready"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ModelRegistry:
    """Central registry for all research models.

    Manages model metadata, version tracking, and lifecycle across
    the research platform.

    Usage::

        registry = ModelRegistry(config={"storage_backend": "s3://..."})
        await registry.initialize()
        model_id = await registry.register_model(
            name="momentum_predictor_v2",
            model_type=ModelType.ML,
            description="GBDT-based momentum predictor",
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        registry_id: Optional[str] = None,
    ) -> None:
        self._id: str = registry_id or f"mreg-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: ModelRegistryState = ModelRegistryState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Storage backend
        self._storage_backend: str = self._config.get("storage_backend", "local")

        # Model store
        self._models: Dict[str, Dict[str, Any]] = {}
        self._versions: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._artifacts: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> ModelRegistryState:
        return self._state

    @property
    def model_count(self) -> int:
        return len(self._models)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the model registry."""
        self._state = ModelRegistryState.INITIALIZING
        logger.info("Initializing ModelRegistry [%s] backend=%s", self._id, self._storage_backend)
        await asyncio.sleep(0.01)
        self._state = ModelRegistryState.READY
        logger.info("ModelRegistry initialized [%s]", self._id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with storage backend."""
        return {
            "registry_id": self._id,
            "backend": self._storage_backend,
            "models": len(self._models),
            "total_versions": sum(len(v) for v in self._versions.values()),
            "artifacts": len(self._artifacts),
        }

    async def shutdown(self) -> None:
        """Clean up registry."""
        logger.info("Shutting down ModelRegistry [%s]...", self._id)
        self._models.clear()
        self._versions.clear()
        self._artifacts.clear()
        self._state = ModelRegistryState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Model Registration
    # ------------------------------------------------------------------

    async def register_model(
        self,
        name: str,
        model_type: ModelType,
        *,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new model in the registry.

        Args:
            name: Unique model name.
            model_type: Type of model.
            description: Human-readable description.
            tags: Searchable tags.
            metadata: Additional metadata.

        Returns:
            Model ID.
        """
        model_id = f"model-{uuid4().hex[:12]}"
        self._models[model_id] = {
            "id": model_id,
            "name": name,
            "type": model_type.value,
            "description": description or "",
            "tags": tags or [],
            "metadata": metadata or {},
            "status": ModelStatus.DRAFT.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._versions[model_id] = []
        logger.info("Model registered: %s [%s] type=%s", model_id, name, model_type.value)
        return model_id

    async def get_model(self, model_id: str) -> Dict[str, Any]:
        """Get model details."""
        model = self._models.get(model_id)
        if model is None:
            raise KeyError(f"Model not found: {model_id}")
        return dict(model)

    async def update_model(
        self,
        model_id: str,
        *,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[ModelStatus] = None,
    ) -> None:
        """Update model metadata."""
        model = self._models.get(model_id)
        if model is None:
            raise KeyError(f"Model not found: {model_id}")

        if description is not None:
            model["description"] = description
        if tags is not None:
            model["tags"] = tags
        if status is not None:
            model["status"] = status.value
        model["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Model updated: %s", model_id)

    async def list_models(
        self,
        model_type: Optional[ModelType] = None,
        status: Optional[ModelStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List models with optional filtering."""
        models = list(self._models.values())
        if model_type is not None:
            models = [m for m in models if m["type"] == model_type.value]
        if status is not None:
            models = [m for m in models if m["status"] == status.value]
        return [
            {"id": m["id"], "name": m["name"], "type": m["type"], "status": m["status"]}
            for m in models
        ]

    async def delete_model(self, model_id: str) -> None:
        """Delete a model and all its versions."""
        if model_id not in self._models:
            raise KeyError(f"Model not found: {model_id}")
        del self._models[model_id]
        self._versions.pop(model_id, None)
        # Clean up associated artifacts
        artifact_keys = [k for k in self._artifacts if k.startswith(model_id)]
        for key in artifact_keys:
            del self._artifacts[key]
        logger.info("Model deleted: %s", model_id)

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    async def create_version(
        self,
        model_id: str,
        *,
        version_name: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new version of a model.

        Args:
            model_id: Parent model ID.
            version_name: Optional version label.
            metrics: Evaluation metrics for this version.
            params: Training parameters.

        Returns:
            Version ID.
        """
        model = self._models.get(model_id)
        if model is None:
            raise KeyError(f"Model not found: {model_id}")

        version_num = len(self._versions[model_id]) + 1
        version_id = f"{model_id}-v{version_num}"

        version = {
            "id": version_id,
            "model_id": model_id,
            "version": version_num,
            "version_name": version_name or f"v{version_num}",
            "metrics": metrics or {},
            "params": params or {},
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._versions[model_id].append(version)

        model["latest_version"] = version_num
        model["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("Version created: %s (v%d)", version_id, version_num)
        return version_id

    async def get_version(self, model_id: str, version: int) -> Dict[str, Any]:
        """Get a specific version of a model."""
        versions = self._versions.get(model_id, [])
        for v in versions:
            if v["version"] == version:
                return dict(v)
        raise KeyError(f"Version {version} not found for model {model_id}")

    async def get_latest_version(self, model_id: str) -> Dict[str, Any]:
        """Get the latest version of a model."""
        versions = self._versions.get(model_id, [])
        if not versions:
            raise KeyError(f"No versions for model {model_id}")
        return dict(versions[-1])

    async def list_versions(self, model_id: str) -> List[Dict[str, Any]]:
        """List all versions of a model."""
        return [dict(v) for v in self._versions.get(model_id, [])]

    # ------------------------------------------------------------------
    # Artifact Management
    # ------------------------------------------------------------------

    async def register_artifact(
        self,
        model_id: str,
        version: int,
        artifact_path: str,
        *,
        artifact_type: str = "model_weights",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a model artifact.

        Args:
            model_id: Model ID.
            version: Model version.
            artifact_path: Path to artifact in storage.
            artifact_type: Type of artifact (weights, config, tokenizer, etc.).
            metadata: Additional artifact metadata.

        Returns:
            Artifact ID.
        """
        artifact_id = f"art-{uuid4().hex[:16]}"
        self._artifacts[artifact_id] = {
            "id": artifact_id,
            "model_id": model_id,
            "version": version,
            "artifact_type": artifact_type,
            "artifact_path": artifact_path,
            "metadata": metadata or {},
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Artifact registered: %s [%s v%d]", artifact_id, model_id, version)
        return artifact_id

    async def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Get artifact details."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return dict(artifact)

    async def list_artifacts(self, model_id: str, version: Optional[int] = None) -> List[Dict[str, Any]]:
        """List artifacts for a model version."""
        artifacts = [a for a in self._artifacts.values() if a["model_id"] == model_id]
        if version is not None:
            artifacts = [a for a in artifacts if a["version"] == version]
        return [dict(a) for a in artifacts]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_models(self, query: str) -> List[Dict[str, Any]]:
        """Search models by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for model in self._models.values():
            if (
                query_lower in model["name"].lower()
                or query_lower in model["description"].lower()
                or any(query_lower in tag.lower() for tag in model["tags"])
            ):
                results.append({"id": model["id"], "name": model["name"], "type": model["type"]})
        return results

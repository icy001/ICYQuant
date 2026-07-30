"""Artifact Storage - Persist models, reports, and training outputs.

Unified storage for all ML artifacts including model binaries, feature importance
reports, evaluation reports, confusion matrices, backtest results, and performance reports.

Usage::

    manager = ArtifactManager()
    artifact = manager.save_artifact(
        experiment_id="exp_001",
        name="model",
        artifact_type=ArtifactType.MODEL,
        data=b"...",
        format="pkl",
    )
    manager.list_artifacts(experiment_id="exp_001")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import uuid


class ArtifactType(str, Enum):
    """Types of ML artifacts."""

    MODEL = "model"
    FEATURE_IMPORTANCE = "feature_importance"
    EVALUATION_REPORT = "evaluation_report"
    CONFUSION_MATRIX = "confusion_matrix"
    BACKTEST_RESULT = "backtest_result"
    PERFORMANCE_REPORT = "performance_report"
    TRAINING_LOG = "training_log"
    HYPERPARAMETER_SEARCH = "hyperparameter_search"
    DATASET_SNAPSHOT = "dataset_snapshot"
    CUSTOM = "custom"


@dataclass
class Artifact:
    """A stored artifact from an ML run.

    Attributes:
        id: Unique artifact identifier.
        experiment_id: Parent experiment ID.
        run_id: Parent run ID (optional).
        name: Artifact name (e.g. "model", "feature_importance_report").
        artifact_type: Category of artifact.
        format: File format (e.g. "pkl", "csv", "json", "pdf", "onnx").
        data: Raw artifact data (in-memory storage).
        size_bytes: Size in bytes.
        created_at: ISO 8601 creation timestamp.
        tags: Arbitrary key-value tags.
        metadata: Additional metadata.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    run_id: str = ""
    name: str = ""
    artifact_type: ArtifactType = ArtifactType.CUSTOM
    format: str = ""
    data: bytes = field(default_factory=bytes)
    size_bytes: int = 0
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary (excludes raw data)."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "tags": dict(self.tags),
            "metadata": dict(self.metadata),
        }


class ArtifactManager:
    """Manages ML artifacts across the platform.

    Supports save, retrieval, listing, search, and cleanup of artifacts.
    All artifacts are associated with experiments and optionally with specific runs.

    Usage::

        manager = ArtifactManager()
        artifact = manager.save_artifact("exp_1", "model", ArtifactType.MODEL, data, "pkl")
        artifacts = manager.list_by_experiment("exp_1")
    """

    def __init__(self) -> None:
        self._artifacts: Dict[str, Artifact] = {}

    # ---- Save ----

    def save_artifact(
        self,
        experiment_id: str,
        name: str,
        artifact_type: ArtifactType,
        data: bytes,
        format: str = "",
        run_id: str = "",
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """Save an artifact to storage.

        Args:
            experiment_id: Parent experiment ID.
            name: Human-readable artifact name.
            artifact_type: Type of artifact.
            data: Raw binary data.
            format: File format extension.
            run_id: Optional parent run ID.
            tags: Key-value tags.
            metadata: Additional metadata.

        Returns:
            The saved Artifact.
        """
        artifact = Artifact(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            artifact_type=artifact_type,
            format=format,
            data=data,
            size_bytes=len(data),
            tags=dict(tags or {}),
            metadata=dict(metadata or {}),
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def save_artifacts_batch(
        self,
        artifacts: List[Dict[str, Any]],
    ) -> List[Artifact]:
        """Save multiple artifacts at once.

        Each dict should have: experiment_id, name, artifact_type, data,
        and optional format, run_id, tags, metadata.
        """
        results = []
        for item in artifacts:
            art = self.save_artifact(
                experiment_id=str(item["experiment_id"]),
                name=str(item["name"]),
                artifact_type=ArtifactType(str(item["artifact_type"])) if not isinstance(item["artifact_type"], ArtifactType) else item["artifact_type"],
                data=item["data"] if isinstance(item["data"], bytes) else bytes(item["data"]),
                format=str(item.get("format", "")),
                run_id=str(item.get("run_id", "")),
                tags=item.get("tags"),
                metadata=item.get("metadata"),
            )
            results.append(art)
        return results

    # ---- Retrieve ----

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact by ID."""
        return self._artifacts.get(artifact_id)

    def get_artifact_data(self, artifact_id: str) -> Optional[bytes]:
        """Retrieve only the raw data of an artifact."""
        art = self._artifacts.get(artifact_id)
        return art.data if art else None

    # ---- List ----

    def list_by_experiment(self, experiment_id: str) -> List[Artifact]:
        """List all artifacts for an experiment."""
        return [a for a in self._artifacts.values() if a.experiment_id == experiment_id]

    def list_by_run(self, experiment_id: str, run_id: str) -> List[Artifact]:
        """List all artifacts for a specific run."""
        return [a for a in self._artifacts.values() if a.experiment_id == experiment_id and a.run_id == run_id]

    def list_by_type(self, artifact_type: ArtifactType) -> List[Artifact]:
        """List all artifacts of a given type."""
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def list_by_name(self, name: str) -> List[Artifact]:
        """List all artifacts with a given name."""
        return [a for a in self._artifacts.values() if a.name == name]

    def list_all(self) -> List[Artifact]:
        """List all stored artifacts."""
        return list(self._artifacts.values())

    def search_artifacts(
        self,
        experiment_id: str = "",
        artifact_type: Optional[ArtifactType] = None,
        name_contains: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> List[Artifact]:
        """Search artifacts with multiple filters."""
        results = list(self._artifacts.values())
        if experiment_id:
            results = [a for a in results if a.experiment_id == experiment_id]
        if artifact_type:
            results = [a for a in results if a.artifact_type == artifact_type]
        if name_contains:
            results = [a for a in results if name_contains.lower() in a.name.lower()]
        if tags:
            results = [a for a in results if all(a.tags.get(k) == v for k, v in tags.items())]
        return results

    # ---- Cleanup ----

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact by ID."""
        return self._artifacts.pop(artifact_id, None) is not None

    def delete_by_experiment(self, experiment_id: str) -> int:
        """Delete all artifacts for an experiment. Returns count deleted."""
        to_delete = [aid for aid, a in self._artifacts.items() if a.experiment_id == experiment_id]
        for aid in to_delete:
            del self._artifacts[aid]
        return len(to_delete)

    def count(self) -> int:
        """Total number of stored artifacts."""
        return len(self._artifacts)

    def total_size_bytes(self) -> int:
        """Total size of all artifacts in bytes."""
        return sum(a.size_bytes for a in self._artifacts.values())

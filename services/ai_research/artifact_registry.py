"""
ICYQuant Artifact Registry — research artifact storage and versioning.

Manages research artifacts (models, charts, datasets, reports) with
versioning, metadata, and provenance tracking for reproducibility.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ArtifactType(str, Enum):
    MODEL = "model"
    CHART = "chart"
    DATASET = "dataset"
    REPORT = "report"
    NOTEBOOK = "notebook"
    CONFIG = "config"
    CODE = "code"
    OTHER = "other"


class ArtifactFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    PNG = "png"
    HTML = "html"
    PICKLE = "pickle"
    HDF5 = "hdf5"
    BINARY = "binary"


@dataclass
class Artifact:
    """A research artifact with versioning."""
    artifact_id: str
    name: str
    artifact_type: ArtifactType
    format: ArtifactFormat
    content_hash: str = ""
    size_bytes: int = 0
    uri: str = ""
    version: int = 1
    session_id: str = ""
    experiment_id: str = ""
    notebook_id: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_artifact_id: str = ""


class ArtifactRegistry:
    """Research artifact storage and versioning system.

    Responsibilities:
        - Register artifacts with metadata
        - Track artifact provenance (session → experiment → artifact)
        - Version artifacts for lineage tracking
        - Content hashing for integrity verification
        - Search and retrieval by tags/type/session
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}
        self._type_index: dict[ArtifactType, list[str]] = {t: [] for t in ArtifactType}
        self._total_registered = 0

    def register(
        self,
        name: str,
        artifact_type: ArtifactType,
        format: ArtifactFormat,
        content: Optional[bytes] = None,
        content_str: str = "",
        uri: str = "",
        session_id: str = "",
        experiment_id: str = "",
        notebook_id: str = "",
        description: str = "",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Artifact:
        """Register a new artifact."""
        import uuid

        # Compute content hash
        data = content or content_str.encode()
        content_hash = hashlib.sha256(data).hexdigest()

        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            name=name,
            artifact_type=artifact_type,
            format=format,
            content_hash=content_hash,
            size_bytes=len(data),
            uri=uri,
            session_id=session_id,
            experiment_id=experiment_id,
            notebook_id=notebook_id,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._artifacts[artifact.artifact_id] = artifact
        self._type_index[artifact_type].append(artifact.artifact_id)
        self._total_registered += 1
        logger.info("Registered artifact: %s [%s]", artifact.artifact_id, artifact_type.value)
        return artifact

    def get(self, artifact_id: str) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)

    def list_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        """List artifacts by type."""
        ids = self._type_index.get(artifact_type, [])
        return [self._artifacts[aid] for aid in ids if aid in self._artifacts]

    def list_by_session(self, session_id: str) -> list[Artifact]:
        """List artifacts for a research session."""
        return [a for a in self._artifacts.values() if a.session_id == session_id]

    def list_by_experiment(self, experiment_id: str) -> list[Artifact]:
        """List artifacts for an experiment."""
        return [a for a in self._artifacts.values() if a.experiment_id == experiment_id]

    def list_by_tag(self, tag: str) -> list[Artifact]:
        """List artifacts by tag."""
        return [a for a in self._artifacts.values() if tag in a.tags]

    def search(self, query: str, limit: int = 20) -> list[Artifact]:
        """Search artifacts by name or description."""
        query_lower = query.lower()
        results = [
            a for a in self._artifacts.values()
            if query_lower in a.name.lower() or query_lower in a.description.lower()
        ]
        return results[:limit]

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact."""
        artifact = self._artifacts.pop(artifact_id, None)
        if artifact:
            self._type_index[artifact.artifact_type].remove(artifact_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        by_type = {t.value: len(ids) for t, ids in self._type_index.items()}
        total_size = sum(a.size_bytes for a in self._artifacts.values())
        return {
            "total_artifacts": len(self._artifacts),
            "total_size_bytes": total_size,
            "by_type": by_type,
            "total_registered": self._total_registered,
        }

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    @property
    def total_registered(self) -> int:
        return self._total_registered

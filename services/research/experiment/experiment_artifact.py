"""Experiment Artifact — represents outputs produced by experiment runs.

Artifacts are the tangible outputs of research including:
* Reports (PDF, HTML)
* Data files (CSV, Parquet)
* Model files
* Visualizations
* Logs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class ArtifactType(str, Enum):
    """Types of experiment artifacts."""

    REPORT = "report"
    DATA = "data"
    MODEL = "model"
    VISUALIZATION = "visualization"
    LOG = "log"
    CONFIG = "config"
    METRICS = "metrics"
    NOTEBOOK = "notebook"
    OTHER = "other"


@dataclass
class ExperimentArtifact:
    """Represents an output artifact from an experiment run.

    Artifacts are versioned, taggable, and carry metadata for
    discoverability and lineage tracking.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    run_id: Optional[str] = None
    name: str = ""
    artifact_type: ArtifactType = ArtifactType.OTHER
    format: str = ""  # pdf, csv, pkl, png, etc.
    path: str = ""
    size_bytes: int = 0
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: list = field(default_factory=list)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_report(self) -> bool:
        return self.artifact_type == ArtifactType.REPORT

    @property
    def is_model(self) -> bool:
        return self.artifact_type == ArtifactType.MODEL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "format": self.format,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "metadata": self.metadata,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentArtifact":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id", str(uuid4())),
            experiment_id=data.get("experiment_id", ""),
            run_id=data.get("run_id"),
            name=data.get("name", ""),
            artifact_type=ArtifactType(data.get("artifact_type", "other")),
            format=data.get("format", ""),
            path=data.get("path", ""),
            size_bytes=data.get("size_bytes", 0),
            checksum=data.get("checksum", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            version=data.get("version", 1),
            created_at=created_at or datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return f"ExperimentArtifact(name={self.name!r}, type={self.artifact_type.value})"

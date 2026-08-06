"""Experiment Version — tracks configuration and metadata versions of experiments.

Each version is an immutable point-in-time snapshot of the experiment
configuration, enabling reproducible research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class ExperimentVersion:
    """Immutable snapshot of an experiment at a point in time.

    Each version captures:
    * The exact configuration used
    * Parent version for lineage
    * Metadata about what changed
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    version: int = 1
    parent_version: Optional[int] = None
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None

    @property
    def is_root(self) -> bool:
        return self.parent_version is None

    @property
    def version_label(self) -> str:
        return f"v{self.version}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "version": self.version,
            "parent_version": self.parent_version,
            "config": self.config,
            "status": self.status,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentVersion":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id", str(uuid4())),
            experiment_id=data.get("experiment_id", ""),
            version=data.get("version", 1),
            parent_version=data.get("parent_version"),
            config=data.get("config", {}),
            status=data.get("status", "active"),
            description=data.get("description", ""),
            created_at=created_at or datetime.now(timezone.utc),
            created_by=data.get("created_by"),
        )

    def __repr__(self) -> str:
        return f"ExperimentVersion(exp={self.experiment_id[:8]}, {self.version_label})"

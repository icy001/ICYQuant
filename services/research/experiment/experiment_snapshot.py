"""Experiment Snapshot — complete point-in-time capture of experiment state.

A snapshot includes:
* Experiment metadata
* Configuration at snapshot time
* Dataset version reference
* Result references
* Environment information
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class ExperimentSnapshot:
    """Complete point-in-time capture of an experiment for reproducibility.

    Snapshots are immutable records that enable:
    * Exact reproduction of experiment runs
    * Audit trail of experiment evolution
    * Comparison across time points
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    version: int = 1
    run_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    dataset_version: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, str] = field(default_factory=dict)
    result_refs: List[str] = field(default_factory=list)
    artifact_refs: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "version": self.version,
            "run_id": self.run_id,
            "config": self.config,
            "dataset_version": self.dataset_version,
            "environment": self.environment,
            "dependencies": self.dependencies,
            "result_refs": self.result_refs,
            "artifact_refs": self.artifact_refs,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentSnapshot":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id", str(uuid4())),
            experiment_id=data.get("experiment_id", ""),
            version=data.get("version", 1),
            run_id=data.get("run_id"),
            config=data.get("config", {}),
            dataset_version=data.get("dataset_version"),
            environment=data.get("environment", {}),
            dependencies=data.get("dependencies", {}),
            result_refs=data.get("result_refs", []),
            artifact_refs=data.get("artifact_refs", []),
            created_at=created_at or datetime.now(timezone.utc),
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )

    def __repr__(self) -> str:
        return f"ExperimentSnapshot(exp={self.experiment_id[:8]}, v{self.version})"

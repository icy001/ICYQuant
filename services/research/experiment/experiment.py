"""Experiment — core domain model for research experiments.

An Experiment represents a single research investigation with:
* A unique identifier and human-readable name
* Configuration parameters
* Dataset reference
* Lifecycle status tracking
* Version history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ExperimentStatus(str, Enum):
    """Experiment lifecycle states."""

    CREATED = "created"
    CONFIGURED = "configured"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
    PUBLISHED = "published"


@dataclass
class Experiment:
    """Core experiment domain model.

    An experiment captures the full lifecycle of a research investigation,
    from creation through execution to publication.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    experiment_type: str = "default"
    dataset: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ExperimentStatus = ExperimentStatus.CREATED
    version: int = 1
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # ── status transitions ────────────────────────────────────────────────

    _valid_transitions: Dict[ExperimentStatus, List[ExperimentStatus]] = field(
        default_factory=lambda: {
            ExperimentStatus.CREATED: [ExperimentStatus.CONFIGURED, ExperimentStatus.ARCHIVED],
            ExperimentStatus.CONFIGURED: [ExperimentStatus.QUEUED, ExperimentStatus.ARCHIVED],
            ExperimentStatus.QUEUED: [ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED],
            ExperimentStatus.RUNNING: [ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED],
            ExperimentStatus.PAUSED: [ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED],
            ExperimentStatus.COMPLETED: [ExperimentStatus.PUBLISHED, ExperimentStatus.ARCHIVED],
            ExperimentStatus.FAILED: [ExperimentStatus.QUEUED, ExperimentStatus.ARCHIVED],
            ExperimentStatus.CANCELLED: [ExperimentStatus.QUEUED, ExperimentStatus.ARCHIVED],
            ExperimentStatus.PUBLISHED: [ExperimentStatus.ARCHIVED],
            ExperimentStatus.ARCHIVED: [],
        },
        repr=False,
    )

    def can_transition_to(self, target: ExperimentStatus) -> bool:
        return target in self._valid_transitions.get(self.status, [])

    def transition_to(self, target: ExperimentStatus) -> None:
        if not self.can_transition_to(target):
            raise ValueError(
                f"Cannot transition from {self.status.value} to {target.value}"
            )
        self.status = target
        self.updated_at = datetime.now(timezone.utc)
        if target == ExperimentStatus.RUNNING:
            self.started_at = datetime.now(timezone.utc)
        elif target in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED):
            self.completed_at = datetime.now(timezone.utc)

    # ── serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "experiment_type": self.experiment_type,
            "dataset": self.dataset,
            "config": self.config,
            "tags": self.tags,
            "metadata": self.metadata,
            "status": self.status.value,
            "version": self.version,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experiment":
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            experiment_type=data.get("experiment_type", "default"),
            dataset=data.get("dataset"),
            config=data.get("config", {}),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            status=ExperimentStatus(data.get("status", "created")),
            version=data.get("version", 1),
            parent_id=data.get("parent_id"),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
            started_at=_parse_optional_dt(data.get("started_at")),
            completed_at=_parse_optional_dt(data.get("completed_at")),
        )

    def __repr__(self) -> str:
        return f"Experiment(id={self.id[:8]}, name={self.name!r}, status={self.status.value})"


def _parse_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return datetime.now(timezone.utc)


def _parse_optional_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    return _parse_dt(val)

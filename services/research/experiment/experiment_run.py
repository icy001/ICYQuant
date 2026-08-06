"""Experiment Run — tracks individual execution attempts of an experiment.

Each run captures the full execution lifecycle including configuration,
timing, results, and any errors encountered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class RunStatus(str, Enum):
    """Run lifecycle states."""

    PENDING = "pending"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExperimentRun:
    """Represents a single execution run of an experiment.

    Tracks:
    * Timing (start, end, duration)
    * Configuration (possibly overriding experiment defaults)
    * Results and metrics
    * Error information on failure
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    status: RunStatus = RunStatus.PENDING
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        )

    @property
    def is_active(self) -> bool:
        return self.status in (RunStatus.QUEUED, RunStatus.INITIALIZING, RunStatus.RUNNING, RunStatus.PAUSED)

    def start(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.status = RunStatus.RUNNING

    def complete(self, result: Optional[Dict[str, Any]] = None) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = RunStatus.SUCCEEDED
        self.result = result
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def fail(self, error: str) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = RunStatus.FAILED
        self.error = error
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def cancel(self) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = RunStatus.CANCELLED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "status": self.status.value,
            "config": self.config,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "result": self.result,
            "error": self.error,
            "metrics": self.metrics,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"ExperimentRun(id={self.id[:8]}, exp={self.experiment_id[:8]}, status={self.status.value})"

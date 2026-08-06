"""Execution record model — tracks each job execution instance."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ExecutionState(str, enum.Enum):
    """Execution lifecycle state."""

    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionResult(str, enum.Enum):
    """Execution outcome."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ExecutionRecord:
    """Immutable execution record.

    Tracks a single execution instance of a scheduled job,
    including timing, outcome, and resource usage.
    """

    execution_id: str
    schedule_id: str
    job_id: str
    worker_id: Optional[str] = None
    state: ExecutionState = ExecutionState.PENDING
    result: Optional[ExecutionResult] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    attempt: int = 1
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    resource_used: Dict[str, float] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_terminal(self) -> bool:
        """Check if this execution has reached a terminal state."""
        return self.state in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMEOUT,
        )

    def mark_started(self, worker_id: str) -> ExecutionRecord:
        """Return a copy marked as started."""
        now = datetime.now(timezone.utc)
        return ExecutionRecord(
            execution_id=self.execution_id,
            schedule_id=self.schedule_id,
            job_id=self.job_id,
            worker_id=worker_id,
            state=ExecutionState.RUNNING,
            result=self.result,
            payload=self.payload,
            output=self.output,
            error_message=self.error_message,
            trace_id=self.trace_id,
            attempt=self.attempt,
            started_at=now,
            completed_at=self.completed_at,
            duration_ms=self.duration_ms,
            resource_used=self.resource_used,
            events=self.events,
            labels=self.labels,
            tags=self.tags,
            created_at=self.created_at,
        )

    def mark_completed(
        self, result: ExecutionResult, output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> ExecutionRecord:
        """Return a copy marked as completed (success or failure)."""
        now = datetime.now(timezone.utc)
        duration = (
            (now - self.started_at).total_seconds() * 1000
            if self.started_at else None
        )
        state = ExecutionState.COMPLETED if result == ExecutionResult.SUCCESS else ExecutionState.FAILED
        return ExecutionRecord(
            execution_id=self.execution_id,
            schedule_id=self.schedule_id,
            job_id=self.job_id,
            worker_id=self.worker_id,
            state=state,
            result=result,
            payload=self.payload,
            output=output or self.output,
            error_message=error or self.error_message,
            trace_id=self.trace_id,
            attempt=self.attempt,
            started_at=self.started_at,
            completed_at=now,
            duration_ms=duration,
            resource_used=self.resource_used,
            events=self.events,
            labels=self.labels,
            tags=self.tags,
            created_at=self.created_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "execution_id": self.execution_id,
            "schedule_id": self.schedule_id,
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "state": self.state.value,
            "result": self.result.value if self.result else None,
            "payload": self.payload,
            "output": self.output,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
            "attempt": self.attempt,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "resource_used": self.resource_used,
            "events": self.events,
            "labels": self.labels,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

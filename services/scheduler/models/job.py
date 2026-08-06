"""Job definition model — a schedulable unit of work."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class JobState(str, enum.Enum):
    """Job lifecycle state."""

    CREATED = "created"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobPriority(int, enum.Enum):
    """Job urgency levels."""

    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass(frozen=True)
class JobConfig:
    """Immutable job configuration."""

    timeout_seconds: Optional[float] = None
    retry_max: int = 3
    retry_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    resource_requirements: Dict[str, float] = field(default_factory=dict)
    worker_affinity: Optional[str] = None
    broadcast: bool = False
    singleton: bool = False


@dataclass(frozen=True)
class JobDefinition:
    """Immutable job descriptor.

    A job is the concrete unit of execution dispatched by the scheduler.
    It maps a schedule trigger to a target workflow or system task.
    """

    job_id: str
    schedule_id: str
    target: str  # workflow_id or task reference
    trigger_type: str
    priority: JobPriority = JobPriority.NORMAL
    state: JobState = JobState.CREATED
    payload: Dict[str, Any] = field(default_factory=dict)
    config: JobConfig = field(default_factory=JobConfig)
    assigned_worker: Optional[str] = None
    trace_id: Optional[str] = None
    parent_job_id: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    scheduled_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_id: Optional[str] = None

    def transition_to(self, new_state: JobState) -> JobDefinition:
        """Return a copy with the given state transition."""
        now = datetime.now(timezone.utc)
        return JobDefinition(
            job_id=self.job_id,
            schedule_id=self.schedule_id,
            target=self.target,
            trigger_type=self.trigger_type,
            priority=self.priority,
            state=new_state,
            payload=self.payload,
            config=self.config,
            assigned_worker=self.assigned_worker,
            trace_id=self.trace_id,
            parent_job_id=self.parent_job_id,
            labels=self.labels,
            tags=self.tags,
            created_at=self.created_at,
            updated_at=now,
            scheduled_at=self.scheduled_at,
            dispatched_at=now if new_state == JobState.DISPATCHED else self.dispatched_at,
            completed_at=now if new_state in (JobState.COMPLETED, JobState.FAILED) else self.completed_at,
            error_message=self.error_message,
            retry_count=self.retry_count,
            execution_id=self.execution_id,
        )

    def with_worker(self, worker_id: str) -> JobDefinition:
        """Return a copy assigned to the given worker."""
        return JobDefinition(
            job_id=self.job_id,
            schedule_id=self.schedule_id,
            target=self.target,
            trigger_type=self.trigger_type,
            priority=self.priority,
            state=self.state,
            payload=self.payload,
            config=self.config,
            assigned_worker=worker_id,
            trace_id=self.trace_id,
            parent_job_id=self.parent_job_id,
            labels=self.labels,
            tags=self.tags,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            scheduled_at=self.scheduled_at,
            dispatched_at=self.dispatched_at,
            completed_at=self.completed_at,
            error_message=self.error_message,
            retry_count=self.retry_count,
            execution_id=self.execution_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "target": self.target,
            "trigger_type": self.trigger_type,
            "priority": self.priority.value,
            "state": self.state.value,
            "payload": self.payload,
            "config": {
                "timeout_seconds": self.config.timeout_seconds,
                "retry_max": self.config.retry_max,
                "retry_delay_seconds": self.config.retry_delay_seconds,
                "backoff_multiplier": self.config.backoff_multiplier,
                "resource_requirements": self.config.resource_requirements,
                "worker_affinity": self.config.worker_affinity,
                "broadcast": self.config.broadcast,
                "singleton": self.config.singleton,
            },
            "assigned_worker": self.assigned_worker,
            "trace_id": self.trace_id,
            "parent_job_id": self.parent_job_id,
            "labels": self.labels,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "dispatched_at": self.dispatched_at.isoformat() if self.dispatched_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "execution_id": self.execution_id,
        }

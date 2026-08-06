"""Schedule definition model — immutable schedule descriptor for the distributed scheduler."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ScheduleType(str, enum.Enum):
    """Category of schedule."""

    CRON = "cron"
    INTERVAL = "interval"
    ONESHOT = "oneshot"
    CALENDAR = "calendar"
    EVENT = "event"
    WORKFLOW = "workflow"


class ScheduleStatus(str, enum.Enum):
    """Schedule lifecycle status."""

    DRAFT = "draft"
    REGISTERED = "registered"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class ScheduleConfig:
    """Immutable schedule configuration."""

    overlapping_policy: str = "skip"  # skip | allow | queue
    misfire_policy: str = "ignore"  # ignore | fire_once | fire_all
    max_concurrent: int = 1
    timeout_seconds: Optional[float] = None
    retry_max: int = 3
    retry_delay_seconds: float = 1.0
    priority: int = 100
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleDefinition:
    """Immutable schedule definition.

    Defines *when* and *where* to trigger a job, without dictating *what* or *how*.
    The workflow engine receives a trigger and decides execution details.
    """

    schedule_id: str
    name: str
    schedule_type: ScheduleType
    trigger_expression: str  # cron expr / ISO interval / event key / calendar rule
    target: str  # workflow_id or system task reference
    payload: Dict[str, Any] = field(default_factory=dict)
    config: ScheduleConfig = field(default_factory=ScheduleConfig)
    status: ScheduleStatus = ScheduleStatus.DRAFT
    version: str = "1.0.0"
    owner: str = ""
    description: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    next_fire_at: Optional[datetime] = None
    last_fire_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    def is_due(self, reference_time: Optional[datetime] = None) -> bool:
        """Check if the schedule is due for execution at the given time."""
        ref = reference_time or datetime.now(timezone.utc)
        if self.status != ScheduleStatus.ACTIVE:
            return False
        if self.end_at and ref >= self.end_at:
            return False
        if self.next_fire_at is None:
            return False
        return ref >= self.next_fire_at

    def with_status(self, status: ScheduleStatus) -> ScheduleDefinition:
        """Return a copy with the given status."""
        return ScheduleDefinition(
            schedule_id=self.schedule_id,
            name=self.name,
            schedule_type=self.schedule_type,
            trigger_expression=self.trigger_expression,
            target=self.target,
            payload=self.payload,
            config=self.config,
            status=status,
            version=self.version,
            owner=self.owner,
            description=self.description,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            next_fire_at=self.next_fire_at,
            last_fire_at=self.last_fire_at,
            end_at=self.end_at,
        )

    def with_next_fire(self, next_fire: datetime) -> ScheduleDefinition:
        """Return a copy with updated next_fire_at."""
        return ScheduleDefinition(
            schedule_id=self.schedule_id,
            name=self.name,
            schedule_type=self.schedule_type,
            trigger_expression=self.trigger_expression,
            target=self.target,
            payload=self.payload,
            config=self.config,
            status=self.status,
            version=self.version,
            owner=self.owner,
            description=self.description,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            next_fire_at=next_fire,
            last_fire_at=self.last_fire_at,
            end_at=self.end_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "trigger_expression": self.trigger_expression,
            "target": self.target,
            "payload": self.payload,
            "config": {
                "overlapping_policy": self.config.overlapping_policy,
                "misfire_policy": self.config.misfire_policy,
                "max_concurrent": self.config.max_concurrent,
                "timeout_seconds": self.config.timeout_seconds,
                "retry_max": self.config.retry_max,
                "retry_delay_seconds": self.config.retry_delay_seconds,
                "priority": self.config.priority,
                "labels": self.config.labels,
                "tags": self.config.tags,
                "metadata": self.config.metadata,
            },
            "status": self.status.value,
            "version": self.version,
            "owner": self.owner,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "next_fire_at": self.next_fire_at.isoformat() if self.next_fire_at else None,
            "last_fire_at": self.last_fire_at.isoformat() if self.last_fire_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
        }

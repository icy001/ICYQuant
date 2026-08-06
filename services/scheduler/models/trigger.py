"""Trigger definition model — describes how a schedule is activated."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TriggerType(str, enum.Enum):
    """Type of trigger mechanism."""

    CRON = "cron"
    INTERVAL = "interval"
    CALENDAR = "calendar"
    EVENT = "event"
    MANUAL = "manual"
    WORKFLOW = "workflow"
    SYSTEM = "system"


class TriggerState(str, enum.Enum):
    """Trigger lifecycle state."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    FIRED = "fired"
    MISFIRED = "misfired"
    QUEUED = "queued"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class TriggerDefinition:
    """Immutable trigger descriptor.

    A trigger evaluates conditions and decides when to fire a job.
    It is the bridge between schedule definitions and job execution.
    """

    trigger_id: str
    schedule_id: str
    trigger_type: TriggerType
    expression: str  # cron / ISO interval / calendar rule / event key
    target: str  # job_id or workflow_id
    state: TriggerState = TriggerState.PENDING
    fired_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    next_evaluation_at: Optional[datetime] = None
    misfire_count: int = 0
    max_misfires: int = 10
    priority: int = 100
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def should_evaluate(self, reference_time: Optional[datetime] = None) -> bool:
        """Determine if the trigger should be re-evaluated now."""
        if self.state in (TriggerState.COMPLETED, TriggerState.FAILED):
            return False
        if self.next_evaluation_at is None:
            return True
        ref = reference_time or datetime.now(timezone.utc)
        return ref >= self.next_evaluation_at

    def mark_fired(self, fired_at: Optional[datetime] = None) -> TriggerDefinition:
        """Return a copy marked as fired."""
        return TriggerDefinition(
            trigger_id=self.trigger_id,
            schedule_id=self.schedule_id,
            trigger_type=self.trigger_type,
            expression=self.expression,
            target=self.target,
            state=TriggerState.FIRED,
            fired_at=fired_at or datetime.now(timezone.utc),
            evaluated_at=self.evaluated_at,
            next_evaluation_at=self.next_evaluation_at,
            misfire_count=self.misfire_count,
            max_misfires=self.max_misfires,
            priority=self.priority,
            payload=self.payload,
            labels=self.labels,
            tags=self.tags,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trigger_id": self.trigger_id,
            "schedule_id": self.schedule_id,
            "trigger_type": self.trigger_type.value,
            "expression": self.expression,
            "target": self.target,
            "state": self.state.value,
            "fired_at": self.fired_at.isoformat() if self.fired_at else None,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "next_evaluation_at": self.next_evaluation_at.isoformat() if self.next_evaluation_at else None,
            "misfire_count": self.misfire_count,
            "max_misfires": self.max_misfires,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

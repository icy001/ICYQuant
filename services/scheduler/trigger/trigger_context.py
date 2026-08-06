"""Trigger Context — execution context passed through the trigger pipeline.

The :class:`TriggerContext` carries metadata from the trigger source all the
way through evaluation, queue, dispatch, and into the scheduler runtime /
workflow engine.  It is designed to be serializable and traceable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class TriggerContext:
    """Context object carried through the entire trigger→dispatch pipeline.

    Fields:
        trigger_id: The trigger that fired.
        schedule_id: The schedule this trigger belongs to.
        execution_id: Unique execution id generated at fire time.
        trigger_time: When the trigger fired (wall-clock).
        scheduled_time: When the trigger was *supposed* to fire (may differ for misfires).
        worker: Assigned worker id (populated by dispatcher).
        trace_id: OpenTelemetry-compatible trace id.
        payload: Arbitrary payload passed through to the workflow.
        labels: Key-value labels for routing/filtering.
        tags: Free-form tags.
    """

    trigger_id: str
    schedule_id: str
    execution_id: str = field(default_factory=lambda: uuid4().hex)
    trigger_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_time: Optional[datetime] = None
    worker: Optional[str] = None
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "schedule_id": self.schedule_id,
            "execution_id": self.execution_id,
            "trigger_time": self.trigger_time.isoformat(),
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "worker": self.worker,
            "trace_id": self.trace_id,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerContext":
        return cls(
            trigger_id=data["trigger_id"],
            schedule_id=data["schedule_id"],
            execution_id=data.get("execution_id", uuid4().hex),
            trigger_time=(
                datetime.fromisoformat(data["trigger_time"])
                if data.get("trigger_time")
                else datetime.now(timezone.utc)
            ),
            scheduled_time=(
                datetime.fromisoformat(data["scheduled_time"])
                if data.get("scheduled_time")
                else None
            ),
            worker=data.get("worker"),
            trace_id=data.get("trace_id", uuid4().hex),
            payload=data.get("payload", {}),
            labels=data.get("labels", {}),
            tags=data.get("tags", []),
        )


def create_trigger_context(
    trigger_id: str,
    schedule_id: str,
    **kwargs: Any,
) -> TriggerContext:
    """Factory helper for creating a trigger context with sensible defaults."""
    return TriggerContext(
        trigger_id=trigger_id,
        schedule_id=schedule_id,
        **kwargs,
    )

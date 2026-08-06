"""Runtime Context — unified execution context for scheduler operations.

The :class:`SchedulerContext` provides the complete execution context
for a scheduled job, including schedule metadata, trigger information,
worker assignment, and tracing data. It can be passed directly to the
Workflow Engine for downstream execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SchedulerContext:
    """Unified execution context for a scheduler-triggered execution.

    Captures all metadata needed to trace, debug, and replay a
    scheduled execution. Designed to be serializable and passable
    across process / network boundaries.

    Usage::

        ctx = SchedulerContext(
            schedule_id="sch_daily_report",
            trigger_time=datetime.now(timezone.utc),
        )
        # Pass to Workflow Engine
        await workflow_engine.execute(ctx)
    """

    def __init__(
        self,
        schedule_id: str,
        trace_id: Optional[str] = None,
        job_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        trigger_time: Optional[datetime] = None,
        trigger_type: str = "unknown",
        worker_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.schedule_id = schedule_id
        self.execution_id = execution_id or str(uuid.uuid4())
        self.trace_id = trace_id or f"trace_{schedule_id}_{self.execution_id[:8]}"
        self.job_id = job_id
        self.trigger_time = trigger_time or datetime.now(timezone.utc)
        self.trigger_type = trigger_type
        self.worker_id = worker_id
        self.variables: Dict[str, Any] = variables or {}
        self.payload: Dict[str, Any] = payload or {}
        self.created_at = datetime.now(timezone.utc)

        # execution timeline
        self._timeline: List[Dict[str, Any]] = []

    def add_timeline_event(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Record a timeline event for tracing."""
        self._timeline.append({
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        })

    def set_variable(self, key: str, value: Any) -> None:
        """Set a context variable."""
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self.variables.get(key, default)

    def assign_worker(self, worker_id: str) -> None:
        """Assign this execution to a specific worker."""
        self.worker_id = worker_id
        self.add_timeline_event("worker_assigned", {"worker_id": worker_id})

    @property
    def timeline(self) -> List[Dict[str, Any]]:
        """Return a copy of the execution timeline."""
        return list(self._timeline)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for transport."""
        return {
            "schedule_id": self.schedule_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "job_id": self.job_id,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "trigger_type": self.trigger_type,
            "worker_id": self.worker_id,
            "variables": self.variables,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "timeline": self._timeline,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SchedulerContext:
        """Reconstruct a context from serialized data."""
        ctx = cls(
            schedule_id=data["schedule_id"],
            trace_id=data.get("trace_id"),
            job_id=data.get("job_id"),
            execution_id=data.get("execution_id"),
            trigger_time=(
                datetime.fromisoformat(data["trigger_time"])
                if data.get("trigger_time") else None
            ),
            trigger_type=data.get("trigger_type", "unknown"),
            worker_id=data.get("worker_id"),
            variables=data.get("variables", {}),
            payload=data.get("payload", {}),
        )
        ctx._timeline = data.get("timeline", [])
        return ctx

    def __repr__(self) -> str:
        return (
            f"SchedulerContext(schedule={self.schedule_id}, "
            f"execution={self.execution_id[:8]}, "
            f"worker={self.worker_id or 'unassigned'})"
        )

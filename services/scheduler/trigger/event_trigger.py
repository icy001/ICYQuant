"""Event Trigger — event-driven scheduling via the ICYQuant EventBus.

The :class:`EventTrigger` listens for specific events on the platform
EventBus and fires when matching events are published.  Supports optional
filter expressions to narrow down which events trigger execution.

Pipeline::

    EventBus → EventTrigger → SchedulerRuntime → Workflow
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class _EvaluationResult:
    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class EventTrigger:
    """Trigger that fires when a specific event is published on the EventBus.

    Usage::

        trigger = EventTrigger(
            schedule_id="sch-on-order-filled",
            event_type="OrderFilled",
            filter_expr={"symbol": "000001.SZ"},
            target="job-post-trade",
        )
    """

    schedule_id: str
    event_type: str  # e.g., OrderFilled, RiskApproved, WorkflowCompleted
    filter_expr: Dict[str, Any] = field(default_factory=dict)
    target: str = ""
    priority: int = 100
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"event_{id(object()):x}")
    trigger_type: str = "event"
    _pending_events: List[Dict[str, Any]] = field(default_factory=list)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # Event ingestion (called by EventBus listener)
    # ------------------------------------------------------------------

    def on_event(self, event: Dict[str, Any]) -> None:
        """Receive an event from the EventBus.

        The event is queued and will be consumed by the next evaluate() call.
        """
        # Apply filter
        if self.filter_expr and not self._matches_filter(event):
            return

        self._pending_events.append(event)

    def _matches_filter(self, event: Dict[str, Any]) -> bool:
        """Check if an event matches the filter expression."""
        for key, expected in self.filter_expr.items():
            actual = event.get(key)
            if actual != expected:
                return False
        return True

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate whether pending events should trigger a fire."""
        try:
            if not self._pending_events:
                return _EvaluationResult(should_fire=False)

            # Pop the first pending event
            event = self._pending_events.pop(0)
            now = datetime.now(timezone.utc)

            # Prevent double-fire within same second
            if self._last_fire_at is not None:
                delta = (now - self._last_fire_at).total_seconds()
                if delta < 1.0:
                    # Re-queue the event
                    self._pending_events.insert(0, event)
                    return _EvaluationResult(should_fire=False)

            self._last_fire_at = now
            self._fire_count += 1

            return _EvaluationResult(
                should_fire=True,
                payload={
                    **self.payload,
                    "event_type": self.event_type,
                    "event_data": event,
                    "trigger_type": "event",
                },
                fire_at=now,
            )

        except Exception as e:
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        return len(self._pending_events)

    def clear_pending(self) -> None:
        self._pending_events.clear()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "event_type": self.event_type,
            "filter_expr": self.filter_expr,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
            "pending_count": len(self._pending_events),
        }

    def __repr__(self) -> str:
        return f"EventTrigger(id={self.trigger_id}, event={self.event_type})"

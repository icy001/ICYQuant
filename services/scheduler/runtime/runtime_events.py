"""Runtime Events — publish/subscribe event bus for scheduler operations.

All scheduler lifecycle events enter the ICYQuant EventBus for
cross-system observability, auditing, and reactive workflows.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SchedulerEventType(str, enum.Enum):
    """Canonical scheduler event types."""

    # Schedule lifecycle
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_UPDATED = "schedule.updated"
    SCHEDULE_PAUSED = "schedule.paused"
    SCHEDULE_RESUMED = "schedule.resumed"
    SCHEDULE_REMOVED = "schedule.removed"

    # Trigger events
    TRIGGER_EVALUATED = "trigger.evaluated"
    TRIGGER_FIRED = "trigger.fired"
    TRIGGER_MISFIRED = "trigger.misfired"
    TRIGGER_SKIPPED = "trigger.skipped"

    # Job lifecycle
    JOB_CREATED = "job.created"
    JOB_QUEUED = "job.queued"
    JOB_DISPATCHED = "job.dispatched"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    JOB_TIMEOUT = "job.timeout"
    JOB_RETRYING = "job.retrying"

    # Runtime events
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_STOPPED = "runtime.stopped"
    RUNTIME_PAUSED = "runtime.paused"
    RUNTIME_RESUMED = "runtime.resumed"
    RUNTIME_DEGRADED = "runtime.degraded"
    RUNTIME_ERROR = "runtime.error"


class SchedulerEvent:
    """Immutable event envelope for the scheduler event bus."""

    def __init__(
        self,
        event_type: SchedulerEventType,
        schedule_id: str,
        data: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        source: str = "scheduler",
    ) -> None:
        self.event_type = event_type
        self.schedule_id = schedule_id
        self.data = data or {}
        self.job_id = job_id
        self.execution_id = execution_id
        self.trace_id = trace_id
        self.source = source
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type.value,
            "schedule_id": self.schedule_id,
            "data": self.data,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


Subscriber = Callable[[SchedulerEvent], None]
AsyncSubscriber = Callable[[SchedulerEvent], Any]  # coroutine or sync


class SchedulerEventBus:
    """In-process publish/subscribe event bus for scheduler operations.

    All events are published synchronously to local subscribers.
    Events can also be forwarded to the external ICYQuant EventBus
    via optional external publisher hooks.

    Usage::

        bus = SchedulerEventBus()
        bus.subscribe(SchedulerEventType.JOB_COMPLETED, on_job_done)
        bus.publish(SchedulerEvent(SchedulerEventType.JOB_COMPLETED, "sch_001"))
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[SchedulerEventType, List[Subscriber]] = {}
        self._global_subscribers: List[Subscriber] = []
        self._external_publishers: List[Callable[[SchedulerEvent], Any]] = []
        self._running: bool = False
        self._event_count: int = 0
        self._history: List[SchedulerEvent] = []
        self._max_history: int = 1000

    def start(self) -> None:
        """Start the event bus."""
        with self._lock:
            self._running = True
        logger.info("SchedulerEventBus: started")

    def stop(self) -> None:
        """Stop the event bus."""
        with self._lock:
            self._running = False
        logger.info("SchedulerEventBus: stopped")

    def subscribe(
        self, event_type: SchedulerEventType, callback: Subscriber,
    ) -> None:
        """Subscribe to a specific event type."""
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    def subscribe_all(self, callback: Subscriber) -> None:
        """Subscribe to all event types."""
        with self._lock:
            self._global_subscribers.append(callback)

    def unsubscribe(
        self, event_type: SchedulerEventType, callback: Subscriber,
    ) -> None:
        """Unsubscribe from a specific event type."""
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    def register_external_publisher(
        self, publisher: Callable[[SchedulerEvent], Any],
    ) -> None:
        """Register an external publisher for forwarding events."""
        with self._lock:
            self._external_publishers.append(publisher)

    def publish(self, event: SchedulerEvent) -> None:
        """Publish an event to all matching subscribers."""
        with self._lock:
            if not self._running:
                return
            self._event_count += 1

            # Record in history (circular buffer)
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            # Snapshot subscribers
            type_subs = list(self._subscribers.get(event.event_type, []))
            global_subs = list(self._global_subscribers)
            externals = list(self._external_publishers)

        # Deliver to type-specific subscribers
        for callback in type_subs + global_subs:
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "SchedulerEventBus: subscriber error for %s", event.event_type.value
                )

        # Forward to external publishers
        for publisher in externals:
            try:
                result = publisher(event)
                if asyncio.iscoroutine(result):
                    # schedule on event loop if available
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception:
                logger.exception("SchedulerEventBus: external publisher error")

    def get_history(
        self, event_type: Optional[SchedulerEventType] = None, limit: int = 100,
    ) -> List[SchedulerEvent]:
        """Retrieve recent event history, optionally filtered."""
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    @property
    def event_count(self) -> int:
        return self._event_count

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for the event bus."""
        return {
            "running": self._running,
            "event_count": self._event_count,
            "history_size": len(self._history),
            "subscriber_counts": {
                k.value: len(v) for k, v in self._subscribers.items()
            },
            "global_subscribers": len(self._global_subscribers),
        }

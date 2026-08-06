"""Scheduler Telemetry — tracing, logging, and metrics pipeline.

Unifies the three pillars of observability:
* Tracing — distributed tracing across scheduler operations
* Logging — structured logging with correlation IDs
* Metrics — Prometheus-compatible metrics export
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class TelemetrySpan:
    """A single tracing span within the scheduler."""

    def __init__(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.span_id = str(uuid.uuid4())[:16]
        self.trace_id = trace_id or str(uuid.uuid4())[:16]
        self.parent_span_id = parent_span_id
        self.metadata = metadata or {}
        self.start_time = time.monotonic()
        self.end_time: Optional[float] = None
        self.duration_seconds: float = 0.0
        self.events: List[Dict[str, Any]] = []
        self.status: str = "ok"

    def add_event(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to this span."""
        self.events.append({
            "name": event_name,
            "timestamp": time.monotonic(),
            "data": data or {},
        })

    def set_error(self, error: Exception) -> None:
        """Mark the span as errored."""
        self.status = "error"
        self.add_event("error", {"type": type(error).__name__, "message": str(error)})

    def finish(self) -> None:
        """Close the span and record duration."""
        self.end_time = time.monotonic()
        self.duration_seconds = self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "events": self.events,
            "metadata": self.metadata,
        }


class SchedulerTelemetry:
    """Unified telemetry for the scheduler.

    Manages tracing spans, structured logging, and metrics
    export for all scheduler operations.

    Records:
    * Trigger Timeline
    * Dispatch Timeline
    * Worker Timeline

    Usage::

        telemetry = SchedulerTelemetry()
        with telemetry.span("evaluate_triggers") as span:
            do_work()
            span.add_event("trigger_fired", {"schedule_id": "sch_001"})
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_spans: Dict[str, TelemetrySpan] = {}
        self._completed_spans: List[Dict[str, Any]] = []
        self._max_completed = 1000
        self._enabled: bool = True

        # Timeline records
        self._trigger_timeline: List[Dict[str, Any]] = []
        self._dispatch_timeline: List[Dict[str, Any]] = []
        self._worker_timeline: List[Dict[str, Any]] = []

    def enable(self) -> None:
        """Enable telemetry collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable telemetry collection."""
        self._enabled = False

    @contextmanager
    def span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[TelemetrySpan, None, None]:
        """Create a new tracing span (context manager).

        Usage::

            with telemetry.span("dispatch_job", trace_id="trace_abc") as span:
                result = await do_dispatch()
                span.add_event("dispatched", {"worker": "w01"})
        """
        if not self._enabled:
            yield TelemetrySpan(name, trace_id, parent_span_id, metadata)
            return

        span_obj = TelemetrySpan(name, trace_id, parent_span_id, metadata)
        with self._lock:
            self._active_spans[span_obj.span_id] = span_obj

        try:
            yield span_obj
        except Exception as exc:
            span_obj.set_error(exc)
            raise
        finally:
            span_obj.finish()
            with self._lock:
                self._active_spans.pop(span_obj.span_id, None)
                self._completed_spans.append(span_obj.to_dict())
                if len(self._completed_spans) > self._max_completed:
                    self._completed_spans = self._completed_spans[-self._max_completed:]

    def record_trigger(self, data: Dict[str, Any]) -> None:
        """Record a trigger event on the trigger timeline."""
        if not self._enabled:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            self._trigger_timeline.append(entry)
            if len(self._trigger_timeline) > self._max_completed:
                self._trigger_timeline = self._trigger_timeline[-self._max_completed:]

    def record_dispatch(self, data: Dict[str, Any]) -> None:
        """Record a dispatch event on the dispatch timeline."""
        if not self._enabled:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            self._dispatch_timeline.append(entry)
            if len(self._dispatch_timeline) > self._max_completed:
                self._dispatch_timeline = self._dispatch_timeline[-self._max_completed:]

    def record_worker(self, data: Dict[str, Any]) -> None:
        """Record a worker event on the worker timeline."""
        if not self._enabled:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            self._worker_timeline.append(entry)
            if len(self._worker_timeline) > self._max_completed:
                self._worker_timeline = self._worker_timeline[-self._max_completed:]

    def get_timelines(self) -> Dict[str, Any]:
        """Return all timeline data."""
        with self._lock:
            return {
                "trigger_timeline": list(self._trigger_timeline),
                "dispatch_timeline": list(self._dispatch_timeline),
                "worker_timeline": list(self._worker_timeline),
            }

    def get_active_spans(self) -> List[Dict[str, Any]]:
        """Return list of currently active spans."""
        with self._lock:
            return [s.to_dict() for s in self._active_spans.values()]

    def get_recent_spans(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recently completed spans."""
        with self._lock:
            return self._completed_spans[-limit:]

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for telemetry."""
        return {
            "enabled": self._enabled,
            "active_spans": len(self._active_spans),
            "completed_spans": len(self._completed_spans),
            "trigger_timeline_events": len(self._trigger_timeline),
            "dispatch_timeline_events": len(self._dispatch_timeline),
            "worker_timeline_events": len(self._worker_timeline),
        }

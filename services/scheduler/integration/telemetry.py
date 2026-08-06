"""Integration Telemetry — platform-level telemetry for the scheduler.

The :class:`IntegrationTelemetry` provides tracing and timeline tracking
for platform integration operations:
* Platform Timeline — end-to-end platform request flow
* Scheduler Timeline — scheduling decisions and dispatch
* Workflow Timeline — workflow execution lifecycle
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class _TimelineSpan:
    """A single span in a timeline."""

    def __init__(self, name: str, parent: Optional["_TimelineSpan"] = None) -> None:
        self.name = name
        self.parent = parent
        self.start_time = time.monotonic()
        self.start_ts = datetime.now(timezone.utc).isoformat()
        self.end_time: Optional[float] = None
        self.end_ts: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self.tags: Dict[str, str] = {}

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_tag(self, key: str, value: str) -> None:
        self.tags[key] = value

    def finish(self) -> None:
        self.end_time = time.monotonic()
        self.end_ts = datetime.now(timezone.utc).isoformat()

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.monotonic() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "duration_ms": round(self.duration_ms, 3),
            "tags": self.tags,
            "events": self.events,
        }


class IntegrationTelemetry:
    """Platform integration telemetry.

    Tracks:
    * Platform Timeline — end-to-end request lifecycle
    * Scheduler Timeline — trigger → dispatch → complete
    * Workflow Timeline — launch → execute → finish
    * Audit Trail — who did what and when

    Usage::

        telemetry = IntegrationTelemetry()
        with telemetry.trace_platform("schedule_job") as span:
            span.add_event("validated")
            # ... do work ...
            span.add_event("dispatched")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_spans: Dict[str, _TimelineSpan] = {}
        self._completed_spans: List[Dict[str, Any]] = []
        self._max_completed = 1000
        self._trace_count: int = 0

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    def trace_platform(self, operation: str) -> _TimelineSpan:
        """Start a platform-level trace span."""
        return self._start_span(f"platform:{operation}")

    def trace_scheduler(self, operation: str) -> _TimelineSpan:
        """Start a scheduler-level trace span."""
        return self._start_span(f"scheduler:{operation}")

    def trace_workflow(self, workflow_id: str) -> _TimelineSpan:
        """Start a workflow-level trace span."""
        return self._start_span(f"workflow:{workflow_id}")

    def trace_adapter(self, adapter_name: str, operation: str) -> _TimelineSpan:
        """Start an adapter-level trace span."""
        return self._start_span(f"adapter:{adapter_name}:{operation}")

    def finish_span(self, span: _TimelineSpan) -> None:
        """Finish a trace span and archive it."""
        span.finish()
        with self._lock:
            self._completed_spans.append(span.to_dict())
            if len(self._completed_spans) > self._max_completed:
                self._completed_spans = self._completed_spans[-self._max_completed:]

    # ------------------------------------------------------------------
    # Timeline Queries
    # ------------------------------------------------------------------

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the most recent completed traces."""
        with self._lock:
            return list(reversed(self._completed_spans[-limit:]))

    def get_active_traces(self) -> List[Dict[str, Any]]:
        """Get currently active traces."""
        with self._lock:
            return [s.to_dict() for s in self._active_spans.values()]

    def get_trace_count(self) -> int:
        return self._trace_count

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _start_span(self, name: str) -> _TimelineSpan:
        with self._lock:
            self._trace_count += 1
            span = _TimelineSpan(name)
            self._active_spans[name] = span
            return span

"""Trigger Telemetry — distributed tracing, logging, and metrics for triggers.

The :class:`TriggerTelemetry` provides:
* OpenTelemetry-compatible tracing spans
* Structured logging with trace context
* Trigger Timeline tracking
* Misfire Timeline tracking
* Trigger delay analysis
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TelemetrySpan:
    """A lightweight tracing span for trigger operations."""

    span_id: str
    trace_id: str
    parent_id: Optional[str] = None
    operation: str = ""
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.perf_counter(),
            "attributes": attributes or {},
        })

    def finish(self) -> None:
        self.end_time = time.perf_counter()


@dataclass
class TriggerTimelineEntry:
    """A single entry in a trigger's fire timeline."""

    trigger_id: str
    trigger_type: str
    fire_time: datetime
    evaluation_duration_ms: float
    queue_wait_ms: float
    dispatch_duration_ms: float
    success: bool
    error: Optional[str] = None


class TriggerTelemetry:
    """Telemetry collector for the trigger engine.

    Usage::

        telemetry = TriggerTelemetry()
        span = telemetry.start_span("evaluate", trace_id="abc123")
        # ... work ...
        span.finish()
    """

    def __init__(self, max_timeline_entries: int = 100_000) -> None:
        self._lock = threading.RLock()
        self._max_timeline = max_timeline_entries

        # Active spans
        self._spans: Dict[str, TelemetrySpan] = {}

        # Timelines
        self._trigger_timeline: List[TriggerTimelineEntry] = []
        self._misfire_timeline: List[Dict[str, Any]] = []

        # Delay analysis (circular buffer of recent delays in ms)
        self._delay_buffer: List[float] = []
        self._max_delay_buffer = 10_000

    # ------------------------------------------------------------------
    # Span management
    # ------------------------------------------------------------------

    def start_span(
        self,
        operation: str,
        trace_id: str = "",
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySpan:
        import uuid
        span_id = uuid.uuid4().hex[:16]
        span = TelemetrySpan(
            span_id=span_id,
            trace_id=trace_id or uuid.uuid4().hex,
            parent_id=parent_id,
            operation=operation,
            attributes=attributes or {},
        )
        with self._lock:
            self._spans[span_id] = span
        return span

    def finish_span(self, span: TelemetrySpan) -> None:
        span.finish()
        with self._lock:
            self._spans.pop(span.span_id, None)

    # ------------------------------------------------------------------
    # Timeline recording
    # ------------------------------------------------------------------

    def record_trigger_fire(self, entry: TriggerTimelineEntry) -> None:
        with self._lock:
            self._trigger_timeline.append(entry)
            if len(self._trigger_timeline) > self._max_timeline:
                self._trigger_timeline = self._trigger_timeline[-self._max_timeline:]

            # Track delay
            delay = entry.queue_wait_ms + entry.evaluation_duration_ms
            self._delay_buffer.append(delay)
            if len(self._delay_buffer) > self._max_delay_buffer:
                self._delay_buffer = self._delay_buffer[-self._max_delay_buffer:]

    def record_misfire(
        self,
        trigger_id: str,
        scheduled_time: datetime,
        detected_at: datetime,
        recovered: bool,
    ) -> None:
        with self._lock:
            self._misfire_timeline.append({
                "trigger_id": trigger_id,
                "scheduled_time": scheduled_time.isoformat(),
                "detected_at": detected_at.isoformat(),
                "delay_seconds": (detected_at - scheduled_time).total_seconds(),
                "recovered": recovered,
            })
            if len(self._misfire_timeline) > self._max_timeline:
                self._misfire_timeline = self._misfire_timeline[-self._max_timeline:]

    # ------------------------------------------------------------------
    # Delay analysis
    # ------------------------------------------------------------------

    def get_delay_stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._delay_buffer:
                return {"p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
            sorted_delays = sorted(self._delay_buffer)
            n = len(sorted_delays)
            return {
                "p50": sorted_delays[int(n * 0.50)],
                "p95": sorted_delays[int(n * 0.95)],
                "p99": sorted_delays[int(n * 0.99)],
                "max": sorted_delays[-1],
                "avg": sum(sorted_delays) / n,
                "count": n,
            }

    def get_recent_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "trigger_id": e.trigger_id,
                    "trigger_type": e.trigger_type,
                    "fire_time": e.fire_time.isoformat(),
                    "evaluation_ms": e.evaluation_duration_ms,
                    "queue_wait_ms": e.queue_wait_ms,
                    "dispatch_ms": e.dispatch_duration_ms,
                    "success": e.success,
                    "error": e.error,
                }
                for e in self._trigger_timeline[-limit:]
            ]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_spans": len(self._spans),
                "timeline_entries": len(self._trigger_timeline),
                "misfire_entries": len(self._misfire_timeline),
                "delay_analysis": self.get_delay_stats(),
            }

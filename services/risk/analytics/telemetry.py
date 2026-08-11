"""
Analytics Telemetry — Distributed tracing and audit logging for risk analytics.

Provides span-based tracing, timeline tracking, and structured audit
logging for all analytics pipeline stages.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A telemetry span representing a unit of work."""
    span_id: str
    trace_id: str
    parent_id: Optional[str]
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "running"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Trace:
    """A full trace containing multiple spans."""
    trace_id: str
    root_span_id: str
    spans: list[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalyticsTelemetry:
    """
    Distributed tracing and audit logging for risk analytics.

    Traces the full analytics pipeline:
    - Scenario Timeline
    - Stress Timeline
    - VaR Timeline
    - Analytics Timeline
    - Report Timeline
    - Audit Trail

    Usage::

        telemetry = AnalyticsTelemetry()
        await telemetry.initialize()

        with telemetry.start_span("var_calculation") as span:
            # ... do work ...
            span.add_event("calculation_complete", {"var": 12345})
    """

    # Pipeline stage names
    PIPELINE_STAGES = [
        "portfolio_load",
        "data_preparation",
        "stress_testing",
        "scenario_loading",
        "scenario_execution",
        "var_calculation",
        "historical_var",
        "parametric_var",
        "montecarlo_var",
        "cvar_calculation",
        "montecarlo_simulation",
        "path_generation",
        "sensitivity_analysis",
        "risk_attribution",
        "factor_decomposition",
        "capital_assessment",
        "report_generation",
        "report_formatting",
        "report_delivery",
    ]

    def __init__(self) -> None:
        self._traces: dict[str, Trace] = {}
        self._active_spans: dict[str, Span] = {}
        self._audit_log: list[dict[str, Any]] = []
        self._max_traces = 1000
        self._max_audit = 5000
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the telemetry system."""
        self._initialized = True
        logger.info("AnalyticsTelemetry initialized.")

    # ---- Trace Management ----

    def start_trace(self, name: str = "analytics_pipeline", metadata: Optional[dict] = None) -> Trace:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        trace = Trace(
            trace_id=trace_id,
            root_span_id="",
            metadata=metadata or {},
        )
        self._traces[trace_id] = trace
        # Evict old traces
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[:len(self._traces) - self._max_traces]
            for k in oldest:
                del self._traces[k]
        return trace

    def end_trace(self, trace_id: str, status: str = "completed") -> None:
        """End a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.end_time = datetime.now(timezone.utc)
            trace.total_duration_ms = (
                (trace.end_time - trace.start_time).total_seconds() * 1000
            )
            trace.status = status

    # ---- Span Management ----

    @contextmanager
    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Iterator[Span]:
        """Start a span as a context manager."""
        span = self._create_span(name, trace_id, parent_id, attributes)
        try:
            yield span
            span.status = "completed"
        except Exception as e:
            span.status = "error"
            span.add_error(str(e))
            raise
        finally:
            span.end_time = datetime.now(timezone.utc)
            span.duration_ms = (
                (span.end_time - span.start_time).total_seconds() * 1000
                if span.end_time
                else 0
            )
            if span.trace_id in self._traces:
                self._traces[span.trace_id].spans.append(span)

    def _create_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Span:
        """Create a new span."""
        span_id = str(uuid.uuid4())
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            if trace_id not in self._traces:
                self._traces[trace_id] = Trace(
                    trace_id=trace_id,
                    root_span_id=span_id,
                )

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_id=parent_id,
            name=name,
            start_time=datetime.now(timezone.utc),
            attributes=attributes or {},
        )
        self._active_spans[span_id] = span
        return span

    # ---- Audit Logging ----

    def audit(
        self,
        action: str,
        actor: str = "system",
        details: Optional[dict[str, Any]] = None,
        status: str = "success",
    ) -> None:
        """Record an audit entry."""
        entry = {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,
            "status": status,
            "details": details or {},
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > self._max_audit:
            self._audit_log = self._audit_log[-self._max_audit:]

    # ---- Query ----

    def get_trace(self, trace_id: str) -> Optional[dict[str, Any]]:
        """Get a trace by ID."""
        trace = self._traces.get(trace_id)
        if not trace:
            return None
        return {
            "trace_id": trace.trace_id,
            "status": trace.status,
            "total_duration_ms": trace.total_duration_ms,
            "span_count": len(trace.spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "error_count": len(s.errors),
                }
                for s in trace.spans
            ],
        }

    def get_recent_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit entries."""
        return self._audit_log[-limit:]

    def get_pipeline_timeline(self, trace_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get a timeline of pipeline stages."""
        if trace_id:
            trace = self._traces.get(trace_id)
            spans = trace.spans if trace else []
        else:
            # Get all recent spans
            spans = []
            for trace in list(self._traces.values())[-10:]:
                spans.extend(trace.spans)

        timeline = []
        for s in sorted(spans, key=lambda x: x.start_time):
            timeline.append({
                "name": s.name,
                "start": s.start_time.isoformat(),
                "duration_ms": s.duration_ms,
                "status": s.status,
                "errors": len(s.errors),
            })
        return timeline

    # ---- Stats ----

    def get_stats(self) -> dict[str, Any]:
        """Get telemetry statistics."""
        traces = list(self._traces.values())
        completed = [t for t in traces if t.status == "completed"]
        failed = [t for t in traces if t.status == "error"]

        durations = [t.total_duration_ms for t in completed if t.total_duration_ms > 0]

        return {
            "total_traces": len(traces),
            "completed_traces": len(completed),
            "failed_traces": len(failed),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "audit_entries": len(self._audit_log),
            "active_spans": len(self._active_spans),
        }

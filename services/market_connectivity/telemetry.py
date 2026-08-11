"""
Connectivity Telemetry — Distributed tracing for the Market Connectivity
Platform covering connection, session, heartbeat, reconnect, and endpoint timelines.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TelemetrySpan:
    """A telemetry span in the connectivity pipeline."""
    span_id: str
    trace_id: str
    name: str
    category: str
    parent_span_id: Optional[str] = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "ok"
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetryTrace:
    """A complete telemetry trace for a connectivity operation."""
    trace_id: str
    spans: list[TelemetrySpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"


class ConnectivityTelemetry:
    """
    Distributed telemetry for the Market Connectivity Platform.

    Provides end-to-end tracing across:
        Connection Timeline → Session Timeline → Heartbeat Timeline
        → Reconnect Timeline → Endpoint Timeline

    Usage::

        telemetry = ConnectivityTelemetry()
        await telemetry.initialize()

        trace = telemetry.start_trace("connect_binance")
        span = telemetry.start_span(trace.trace_id, "websocket_handshake", "connection")
        telemetry.end_span(span.span_id)
        telemetry.end_trace(trace.trace_id)
    """

    CATEGORY_CONNECTION = "connection"
    CATEGORY_SESSION = "session"
    CATEGORY_HEARTBEAT = "heartbeat"
    CATEGORY_RECONNECT = "reconnect"
    CATEGORY_ENDPOINT = "endpoint"
    CATEGORY_AUTH = "authentication"
    CATEGORY_PROTOCOL = "protocol"

    def __init__(self, max_traces: int = 5000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._spans: dict[str, TelemetrySpan] = {}
        self._max_traces = max_traces

    async def initialize(self) -> None:
        """Initialize the telemetry system."""
        logger.info("ConnectivityTelemetry initialized.")

    async def stop(self) -> None:
        """Stop the telemetry system."""
        self._traces.clear()
        self._spans.clear()
        logger.info("ConnectivityTelemetry stopped.")

    # ---- Trace Operations ----

    def start_trace(self, name: str) -> TelemetryTrace:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        trace = TelemetryTrace(trace_id=trace_id)
        self._traces[trace_id] = trace

        if len(self._traces) > self._max_traces:
            oldest = list(self._traces.keys())[0]
            del self._traces[oldest]

        return trace

    def end_trace(self, trace_id: str, status: str = "completed") -> Optional[TelemetryTrace]:
        """End a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.completed_at = datetime.now(timezone.utc)
            trace.status = status
            total_duration = sum(s.duration_ms for s in trace.spans)
            logger.debug(
                "Trace %s completed: %d spans, %.2fms",
                trace_id, len(trace.spans), total_duration,
            )
        return trace

    # ---- Span Operations ----

    def start_span(
        self,
        trace_id: str,
        name: str,
        category: str,
        parent_span_id: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> Optional[TelemetrySpan]:
        """Start a new span within a trace."""
        trace = self._traces.get(trace_id)
        if trace is None:
            return None

        span_id = str(uuid.uuid4())
        span = TelemetrySpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            category=category,
            parent_span_id=parent_span_id,
            tags=tags or {},
        )
        self._spans[span_id] = span
        trace.spans.append(span)

        if len(self._spans) > self._max_traces * 5:
            oldest = list(self._spans.keys())[0]
            del self._spans[oldest]

        return span

    def end_span(self, span_id: str, status: str = "ok", metadata: Optional[dict[str, Any]] = None) -> Optional[TelemetrySpan]:
        """End a span."""
        span = self._spans.get(span_id)
        if span:
            span.ended_at = time.monotonic()
            span.duration_ms = (span.ended_at - span.started_at) * 1000
            span.status = status
            if metadata:
                span.metadata.update(metadata)
        return span

    # ---- Convenience Methods ----

    def trace_connection(
        self, exchange_id: str, protocol: str, endpoint: str
    ) -> tuple[TelemetryTrace, TelemetrySpan]:
        """Start a connection trace with an initial span."""
        trace = self.start_trace(f"connect_{exchange_id}")
        span = self.start_span(
            trace.trace_id,
            f"connect_{exchange_id}",
            self.CATEGORY_CONNECTION,
            tags={"exchange": exchange_id, "protocol": protocol, "endpoint": endpoint},
        )
        return trace, span

    def trace_session(
        self, exchange_id: str, session_type: str, parent_trace_id: Optional[str] = None
    ) -> TelemetryTrace:
        """Start a session trace."""
        trace_id = parent_trace_id or str(uuid.uuid4())
        trace = TelemetryTrace(trace_id=trace_id)
        self._traces[trace.trace_id] = trace
        self.start_span(
            trace.trace_id,
            f"session_{session_type}",
            self.CATEGORY_SESSION,
            tags={"exchange": exchange_id, "session_type": session_type},
        )
        return trace

    # ---- Queries ----

    def get_trace(self, trace_id: str) -> Optional[TelemetryTrace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_span(self, span_id: str) -> Optional[TelemetrySpan]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    def get_timeline(self, trace_id: str) -> list[dict[str, Any]]:
        """Get a chronological timeline of spans in a trace."""
        trace = self._traces.get(trace_id)
        if trace is None:
            return []

        sorted_spans = sorted(trace.spans, key=lambda s: s.started_at)
        return [
            {
                "span_id": s.span_id,
                "name": s.name,
                "category": s.category,
                "started_at": s.started_at,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "tags": s.tags,
            }
            for s in sorted_spans
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get telemetry summary."""
        total_spans = len(self._spans)
        active_traces = sum(1 for t in self._traces.values() if t.status == "running")

        category_counts: dict[str, int] = {}
        for s in self._spans.values():
            category_counts[s.category] = category_counts.get(s.category, 0) + 1

        return {
            "total_traces": len(self._traces),
            "active_traces": active_traces,
            "total_spans": total_spans,
            "spans_by_category": category_counts,
        }

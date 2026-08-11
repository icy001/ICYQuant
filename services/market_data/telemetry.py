"""
Market Data Telemetry — distributed tracing for the normalization
pipeline, data quality framework, and data flow.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    NORMALIZATION = "normalization"
    VALIDATION = "validation"
    QUALITY = "quality"
    PIPELINE = "pipeline"
    CACHE = "cache"
    DETECTION = "detection"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class NormalizationSpan:
    """A trace span for a normalization operation."""

    span_id: str = ""
    trace_id: str = ""
    parent_span_id: str = ""
    kind: SpanKind = SpanKind.NORMALIZATION
    status: SpanStatus = SpanStatus.OK
    name: str = ""

    instrument_id: str = ""
    exchange_id: str = ""
    event_type: str = ""

    start_time_ns: int = 0
    end_time_ns: int = 0
    duration_ns: int = 0

    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""

    @property
    def duration_us(self) -> float:
        return self.duration_ns / 1000.0

    @property
    def duration_ms(self) -> float:
        return self.duration_ns / 1_000_000.0


@dataclass
class PipelineTrace:
    """A complete trace of a data record through the normalization pipeline."""

    trace_id: str = ""
    instrument_id: str = ""
    event_type: str = ""
    exchange_id: str = ""

    spans: list[NormalizationSpan] = field(default_factory=list)
    status: SpanStatus = SpanStatus.OK
    total_duration_ns: int = 0

    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def error_spans(self) -> list[NormalizationSpan]:
        return [s for s in self.spans if s.status == SpanStatus.ERROR]


class MarketDataTelemetry:
    """
    Distributed tracing for market data normalization pipeline.

    Traces:
    - Normalization Timeline: Raw → Canonical conversion
    - Validation Timeline: Schema & data validation
    - Quality Timeline: Quality assessment & scoring
    - Pipeline Timeline: End-to-end pipeline execution
    - Detection Timeline: Duplicate/gap/outlier detection
    """

    def __init__(self, max_traces: int = 10_000) -> None:
        self._max_traces = max_traces
        self._traces: dict[str, PipelineTrace] = {}
        self._active_spans: dict[str, NormalizationSpan] = {}
        self._stats: dict[str, int] = {"total_traces": 0, "total_spans": 0, "error_spans": 0}

    async def initialize(self) -> None:
        logger.info("MarketDataTelemetry initialized (max_traces: %d)", self._max_traces)

    # ── Trace management ───────────────────────────

    async def start_trace(
        self,
        instrument_id: str = "",
        event_type: str = "",
        exchange_id: str = "",
    ) -> PipelineTrace:
        """Start a new pipeline trace."""
        trace_id = str(uuid.uuid4())[:16]
        trace = PipelineTrace(
            trace_id=trace_id,
            instrument_id=instrument_id,
            event_type=event_type,
            exchange_id=exchange_id,
            created_at=datetime.now(timezone.utc),
        )
        self._traces[trace_id] = trace
        self._stats["total_traces"] += 1

        # Prune old traces
        if len(self._traces) > self._max_traces:
            oldest = min(self._traces, key=lambda k: self._traces[k].created_at or datetime.min)
            del self._traces[oldest]

        return trace

    async def start_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str = "",
        instrument_id: str = "",
        exchange_id: str = "",
        parent_span_id: str = "",
    ) -> NormalizationSpan:
        """Start a new span within a trace."""
        span_id = str(uuid.uuid4())[:12]
        span = NormalizationSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name,
            instrument_id=instrument_id,
            exchange_id=exchange_id,
            start_time_ns=self._now_ns(),
            status=SpanStatus.OK,
        )
        self._active_spans[span_id] = span
        self._stats["total_spans"] += 1
        return span

    async def end_span(
        self,
        span_id: str,
        status: SpanStatus = SpanStatus.OK,
        error_message: str = "",
        attributes: Optional[dict[str, Any]] = None,
    ) -> Optional[NormalizationSpan]:
        """End a span and attach it to its trace."""
        span = self._active_spans.pop(span_id, None)
        if span is None:
            logger.warning("Span not found: %s", span_id)
            return None

        span.end_time_ns = self._now_ns()
        span.duration_ns = span.end_time_ns - span.start_time_ns
        span.status = status
        span.error_message = error_message
        if attributes:
            span.attributes.update(attributes)

        if status == SpanStatus.ERROR:
            self._stats["error_spans"] += 1

        # Attach to trace
        trace = self._traces.get(span.trace_id)
        if trace:
            trace.spans.append(span)
            if status == SpanStatus.ERROR:
                trace.status = SpanStatus.ERROR
            trace.total_duration_ns = max(
                trace.total_duration_ns,
                span.end_time_ns - (trace.spans[0].start_time_ns if trace.spans else span.start_time_ns),
            )

        return span

    async def add_span_event(self, span_id: str, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to an active span."""
        span = self._active_spans.get(span_id)
        if span:
            span.events.append({
                "name": name,
                "timestamp_ns": self._now_ns(),
                "attributes": attributes or {},
            })

    # ── Query ──────────────────────────────────────

    async def get_trace(self, trace_id: str) -> Optional[PipelineTrace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    async def get_recent_traces(self, limit: int = 100) -> list[PipelineTrace]:
        """Get recent traces, most recent first."""
        sorted_traces = sorted(
            self._traces.values(),
            key=lambda t: t.created_at or datetime.min,
            reverse=True,
        )
        return sorted_traces[:limit]

    async def get_error_traces(self, limit: int = 50) -> list[PipelineTrace]:
        """Get traces that contain errors."""
        error_traces = [t for t in self._traces.values() if t.status == SpanStatus.ERROR]
        return sorted(
            error_traces,
            key=lambda t: t.created_at or datetime.min,
            reverse=True,
        )[:limit]

    async def get_trace_summary(self) -> dict[str, Any]:
        """Get a summary of trace statistics."""
        traces = list(self._traces.values())
        if not traces:
            return {"total_traces": 0, "total_spans": 0}

        durations = [t.total_duration_ns for t in traces if t.total_duration_ns > 0]
        return {
            "total_traces": len(traces),
            "total_spans": self._stats["total_spans"],
            "error_spans": self._stats["error_spans"],
            "error_traces": sum(1 for t in traces if t.status == SpanStatus.ERROR),
            "avg_pipeline_us": (sum(durations) / len(durations) / 1000) if durations else 0,
            "max_pipeline_us": (max(durations) / 1000) if durations else 0,
            "min_pipeline_us": (min(durations) / 1000) if durations else 0,
        }

    async def clear(self) -> None:
        """Clear all traces."""
        self._traces.clear()
        self._active_spans.clear()
        self._stats = {"total_traces": 0, "total_spans": 0, "error_spans": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)

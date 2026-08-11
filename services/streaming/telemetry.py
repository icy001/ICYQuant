"""
Streaming Telemetry — distributed tracing for the real-time streaming
platform covering stream, window, aggregation, checkpoint, and DLQ timelines.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamSpan:
    """A telemetry span within a streaming trace."""
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
class StreamTrace:
    """A complete telemetry trace."""
    trace_id: str
    operation: str
    spans: list[StreamSpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"


class StreamingTelemetry:
    """
    Distributed telemetry for the streaming platform.

    Provides end-to-end tracing across streaming pipelines:
        Stream Timeline → Window Timeline → Aggregation Timeline
        → Checkpoint Timeline → DLQ Timeline

    Categories:
        - publish: event publishing
        - subscribe: event subscription
        - process: event processing
        - window: window operations
        - aggregation: aggregation operations
        - checkpoint: checkpointing
        - dlq: dead letter queue

    Usage::

        telemetry = StreamingTelemetry()
        trace, span = telemetry.trace_publish("market.tick")
        telemetry.end_span(span.span_id)
        telemetry.end_trace(trace.trace_id)
    """

    def __init__(self, max_traces: int = 10000) -> None:
        self._traces: dict[str, StreamTrace] = {}
        self._spans: dict[str, StreamSpan] = {}
        self._max_traces = max_traces

    async def initialize(self) -> None:
        """Initialize telemetry."""
        logger.info("StreamingTelemetry initialized.")

    async def stop(self) -> None:
        """Stop telemetry."""
        self._traces.clear()
        self._spans.clear()

    def start_trace(self, name: str, operation: str = "generic") -> StreamTrace:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        trace = StreamTrace(trace_id=trace_id, operation=operation)
        self._traces[trace_id] = trace

        if len(self._traces) > self._max_traces:
            oldest = next(iter(self._traces.keys()))
            del self._traces[oldest]

        return trace

    def end_trace(self, trace_id: str, status: str = "completed") -> Optional[StreamTrace]:
        """End a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.completed_at = datetime.now(timezone.utc)
            trace.status = status
        return trace

    def start_span(
        self,
        trace_id: str,
        name: str,
        category: str,
        parent_span_id: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> Optional[StreamSpan]:
        """Start a new span."""
        span_id = str(uuid.uuid4())
        span = StreamSpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            category=category,
            parent_span_id=parent_span_id,
            tags=tags or {},
        )
        self._spans[span_id] = span
        trace = self._traces.get(trace_id)
        if trace:
            trace.spans.append(span)
        return span

    def end_span(
        self, span_id: str, status: str = "ok", metadata: Optional[dict[str, Any]] = None
    ) -> Optional[StreamSpan]:
        """End a span."""
        span = self._spans.get(span_id)
        if span:
            span.ended_at = time.monotonic()
            span.duration_ms = (span.ended_at - span.started_at) * 1000
            span.status = status
            if metadata:
                span.metadata.update(metadata)
        return span

    def trace_publish(self, topic: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a publish trace."""
        trace = self.start_trace(f"publish_{topic}", "publish")
        span = self.start_span(trace.trace_id, f"publish_to_{topic}", "publish", tags={"topic": topic})
        return trace, span

    def trace_subscribe(self, topic: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a subscribe trace."""
        trace = self.start_trace(f"subscribe_{topic}", "subscribe")
        span = self.start_span(trace.trace_id, f"subscribe_to_{topic}", "subscribe", tags={"topic": topic})
        return trace, span

    def trace_process(self, topic: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a processing trace."""
        trace = self.start_trace(f"process_{topic}", "process")
        span = self.start_span(trace.trace_id, f"process_{topic}", "process", tags={"topic": topic})
        return trace, span

    def trace_window(self, window_type: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a window trace."""
        trace = self.start_trace(f"window_{window_type}", "window")
        span = self.start_span(trace.trace_id, f"window_{window_type}", "window", tags={"window_type": window_type})
        return trace, span

    def trace_aggregation(self, agg_type: str) -> tuple[StreamTrace, StreamSpan]:
        """Start an aggregation trace."""
        trace = self.start_trace(f"agg_{agg_type}", "aggregation")
        span = self.start_span(trace.trace_id, f"agg_{agg_type}", "aggregation", tags={"agg_type": agg_type})
        return trace, span

    def trace_checkpoint(self, topic: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a checkpoint trace."""
        trace = self.start_trace(f"checkpoint_{topic}", "checkpoint")
        span = self.start_span(trace.trace_id, f"checkpoint_{topic}", "checkpoint", tags={"topic": topic})
        return trace, span

    def trace_dlq(self, topic: str) -> tuple[StreamTrace, StreamSpan]:
        """Start a DLQ trace."""
        trace = self.start_trace(f"dlq_{topic}", "dlq")
        span = self.start_span(trace.trace_id, f"dlq_{topic}", "dlq", tags={"topic": topic})
        return trace, span

    def get_summary(self) -> dict[str, Any]:
        """Get telemetry summary."""
        category_counts: dict[str, int] = {}
        category_durations: dict[str, float] = {}
        for s in self._spans.values():
            category_counts[s.category] = category_counts.get(s.category, 0) + 1
            category_durations[s.category] = category_durations.get(s.category, 0.0) + s.duration_ms

        return {
            "total_traces": len(self._traces),
            "total_spans": len(self._spans),
            "active_traces": sum(1 for t in self._traces.values() if t.status == "running"),
            "spans_by_category": category_counts,
            "avg_duration_ms_by_category": {
                cat: round(dur / max(category_counts.get(cat, 1), 1), 2)
                for cat, dur in category_durations.items()
            },
        }

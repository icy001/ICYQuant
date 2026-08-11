"""
Trace Manager — Distributed tracing for the Strategy Platform.

Manages trace context propagation, span creation, and trace
aggregation across the full strategy execution pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TraceContext:
    """Distributed trace context."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: dict[str, str] = field(default_factory=dict)


@dataclass
class TraceSpan:
    """A single span in a distributed trace."""
    span_id: str
    trace_id: str
    name: str
    parent_span_id: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "ok"  # ok, error
    tags: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class TraceManager:
    """
    Distributed trace manager for the Strategy Platform.

    Provides trace context propagation, span lifecycle management,
    and trace aggregation for end-to-end observability across
    the strategy execution pipeline.

    Usage::

        tm = TraceManager()
        await tm.initialize()

        # Start a trace
        ctx = await tm.start_trace("strategy_execution")
        span = await tm.start_span(ctx, "signal_generation")
        # ... do work ...
        await tm.end_span(span.span_id)

        # Get trace
        trace = await tm.get_trace(ctx.trace_id)
    """

    def __init__(self, max_traces: int = 10000) -> None:
        self._traces: dict[str, list[TraceSpan]] = {}
        self._spans: dict[str, TraceSpan] = {}
        self._max_traces = max_traces
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the trace manager."""
        self._initialized = True
        logger.info("TraceManager initialized.")

    async def stop(self) -> None:
        """Stop the trace manager."""
        self._initialized = False
        logger.info("TraceManager stopped.")

    # ---- Trace Management ----

    async def start_trace(
        self,
        name: str,
        baggage: Optional[dict[str, str]] = None,
    ) -> TraceContext:
        """Start a new distributed trace."""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        ctx = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            baggage=baggage or {},
        )

        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
        )
        self._spans[span_id] = span
        self._traces.setdefault(trace_id, []).append(span)

        await self._trim_traces()

        logger.debug(f"Trace started: {trace_id} ({name})")
        return ctx

    async def start_span(
        self,
        context: TraceContext,
        name: str,
        tags: Optional[dict[str, str]] = None,
    ) -> TraceSpan:
        """Start a new span within an existing trace."""
        span_id = str(uuid.uuid4())

        span = TraceSpan(
            span_id=span_id,
            trace_id=context.trace_id,
            parent_span_id=context.span_id,
            name=name,
            tags=tags or {},
        )
        self._spans[span_id] = span
        self._traces.setdefault(context.trace_id, []).append(span)

        return span

    async def end_span(
        self,
        span_id: str,
        status: str = "ok",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[TraceSpan]:
        """End a span."""
        span = self._spans.get(span_id)
        if not span:
            return None

        span.ended_at = datetime.now(timezone.utc)
        span.duration_ms = (span.ended_at - span.started_at).total_seconds() * 1000
        span.status = status
        if metadata:
            span.metadata.update(metadata)

        return span

    async def add_span_event(
        self,
        span_id: str,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an event to a span."""
        span = self._spans.get(span_id)
        if span:
            span.events.append({
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": attributes or {},
            })

    async def set_span_tag(self, span_id: str, key: str, value: str) -> None:
        """Set a tag on a span."""
        span = self._spans.get(span_id)
        if span:
            span.tags[key] = value

    # ---- Trace Retrieval ----

    async def get_trace(self, trace_id: str) -> list[TraceSpan]:
        """Get all spans for a trace."""
        return self._traces.get(trace_id, [])

    async def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    async def get_trace_summary(self, trace_id: str) -> Optional[dict[str, Any]]:
        """Get a summary of a trace."""
        spans = self._traces.get(trace_id)
        if not spans:
            return None

        root_span = next((s for s in spans if s.parent_span_id is None), spans[0])
        total_duration = sum(s.duration_ms for s in spans if s.ended_at)
        errors = [s for s in spans if s.status == "error"]

        return {
            "trace_id": trace_id,
            "root_name": root_span.name,
            "span_count": len(spans),
            "total_duration_ms": total_duration,
            "error_count": len(errors),
            "status": "error" if errors else "ok",
        }

    async def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent traces."""
        summaries = []
        for trace_id in list(self._traces.keys())[-limit:]:
            summary = await self.get_trace_summary(trace_id)
            if summary:
                summaries.append(summary)
        return summaries

    # ---- Internal ----

    async def _trim_traces(self) -> None:
        """Trim old traces if over max limit."""
        if len(self._traces) > self._max_traces:
            excess = len(self._traces) - self._max_traces
            keys_to_remove = list(self._traces.keys())[:excess]
            for key in keys_to_remove:
                spans = self._traces.pop(key, [])
                for span in spans:
                    self._spans.pop(span.span_id, None)

    async def health_check(self) -> dict[str, Any]:
        """Check trace manager health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_traces": len(self._traces),
            "active_spans": len(self._spans),
            "max_traces": self._max_traces,
        }

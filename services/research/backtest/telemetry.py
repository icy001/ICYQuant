"""Backtest Telemetry — distributed tracing for backtest operations.

Unified tracing::

    Backtest → Tracing → Metrics → Replay Timeline → Execution Timeline → Audit
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    INTERNAL = "internal"
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class BacktestSpanContext:
    """Span context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    is_remote: bool = False
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class BacktestSpan:
    """A single trace span in a backtest execution."""

    name: str
    context: BacktestSpanContext
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    parent: Optional["BacktestSpan"] = None


class BacktestTracer:
    """Distributed tracing for backtest operations.

    Provides:
    * Span creation and management
    * Context propagation across async boundaries
    * Event logging with timestamps
    * Decorator for automatic tracing
    """

    def __init__(self) -> None:
        self._active_spans: Dict[str, BacktestSpan] = {}
        self._completed_spans: List[BacktestSpan] = []
        self._trace_count = 0

    # ── span management ────────────────────────────────────────────────────

    def start_span(
        self,
        name: str,
        parent_ctx: Optional[BacktestSpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> BacktestSpan:
        """Start a new trace span.

        Args:
            name: Span operation name.
            parent_ctx: Optional parent span context for propagation.
            kind: Span kind.
            attributes: Initial span attributes.

        Returns:
            The started BacktestSpan.
        """
        trace_id = parent_ctx.trace_id if parent_ctx else str(uuid4())
        span_id = str(uuid4())

        ctx = BacktestSpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_ctx.span_id if parent_ctx else None,
        )

        span = BacktestSpan(
            name=name,
            context=ctx,
            kind=kind,
            attributes=attributes or {},
        )

        self._active_spans[span_id] = span
        if trace_id != (parent_ctx.trace_id if parent_ctx else trace_id):
            self._trace_count += 1

        return span

    def end_span(
        self,
        span: BacktestSpan,
        status: SpanStatus = SpanStatus.OK,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """End a span.

        Args:
            span: The span to end.
            status: Final span status.
            attributes: Additional attributes to record.
        """
        span.end_time = time.monotonic()
        span.status = status
        if attributes:
            span.attributes.update(attributes)

        self._active_spans.pop(span.context.span_id, None)
        self._completed_spans.append(span)

        duration_ms = (span.end_time - span.start_time) * 1000
        if duration_ms > 1000:
            logger.debug("Slow span: %s (%.0fms)", span.name, duration_ms)

    def add_event(
        self,
        span: BacktestSpan,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a timestamped event to a span."""
        span.events.append({
            "name": name,
            "timestamp": time.monotonic(),
            "attributes": attributes or {},
        })

    def set_attribute(self, span: BacktestSpan, key: str, value: Any) -> None:
        """Set an attribute on a span."""
        span.attributes[key] = value

    # ── context propagation ────────────────────────────────────────────────

    def get_current_context(self, span: BacktestSpan) -> BacktestSpanContext:
        """Get the span context for propagation."""
        return span.context

    @contextmanager
    def span(self, name: str, parent_ctx: Optional[BacktestSpanContext] = None):
        """Context manager for automatic span start/end.

        Usage::

            with tracer.span("compute_factors", parent_ctx) as sp:
                factors = compute()
                tracer.add_event(sp, "factors_computed", {"count": len(factors)})
        """
        span = self.start_span(name, parent_ctx)
        try:
            yield span
            self.end_span(span, SpanStatus.OK)
        except Exception as e:
            self.end_span(span, SpanStatus.ERROR, {"error": str(e)})
            raise

    # ── decorator ──────────────────────────────────────────────────────────

    def trace(self, name: Optional[str] = None, kind: SpanKind = SpanKind.INTERNAL):
        """Decorator to automatically trace a function.

        Usage::

            @tracer.trace("calculate_backtest")
            async def calculate_backtest(ctx):
                ...
        """
        def decorator(func: Callable):
            span_name = name or func.__name__

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                span = self.start_span(span_name, kind=kind)
                try:
                    result = await func(*args, **kwargs)
                    self.end_span(span, SpanStatus.OK)
                    return result
                except Exception as e:
                    self.end_span(span, SpanStatus.ERROR, {"error": str(e)})
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                span = self.start_span(span_name, kind=kind)
                try:
                    result = func(*args, **kwargs)
                    self.end_span(span, SpanStatus.OK)
                    return result
                except Exception as e:
                    self.end_span(span, SpanStatus.ERROR, {"error": str(e)})
                    raise

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    # ── timeline ───────────────────────────────────────────────────────────

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Generate execution timeline from completed spans."""
        timeline = []
        for span in self._completed_spans:
            timeline.append({
                "name": span.name,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "duration_ms": (span.end_time - span.start_time) * 1000 if span.end_time else 0,
                "status": span.status.value,
                "events": span.events,
            })
        timeline.sort(key=lambda x: x["start_time"])
        return timeline

    # ── query ──────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return tracer statistics."""
        completed = self._completed_spans
        error_spans = [s for s in completed if s.status == SpanStatus.ERROR]
        durations = [(s.end_time - s.start_time) * 1000 for s in completed if s.end_time]

        return {
            "active_spans": len(self._active_spans),
            "completed_spans": len(completed),
            "trace_count": self._trace_count,
            "error_spans": len(error_spans),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
        }

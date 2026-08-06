"""Integration Telemetry — distributed tracing for the unified research platform.

Commit 11 Part 1.5: Provides OpenTelemetry-compatible distributed tracing
across all integration adapters for end-to-end observability.

Architecture::

    Research Platform → Tracing → Metrics → Timeline → Audit

Traces:
    - Experiment Timeline
    - Backtest Timeline
    - Portfolio Timeline
    - Platform Initialization Timeline
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Context variable for span propagation
_current_span: ContextVar[Optional[IntegrationSpan]] = ContextVar("integration_span", default=None)


class IntegrationSpanContext:
    """Distributed tracing span context for cross-service propagation."""

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        *,
        parent_span_id: Optional[str] = None,
        sampled: bool = True,
    ) -> None:
        self.trace_id: str = trace_id
        self.span_id: str = span_id
        self.parent_span_id: Optional[str] = parent_span_id
        self.sampled: bool = sampled

    def to_dict(self) -> Dict[str, str]:
        """Serialize for propagation headers."""
        result = {
            "traceparent": f"00-{self.trace_id}-{self.span_id}-{'01' if self.sampled else '00'}",
        }
        return result


class IntegrationSpan:
    """A single trace span representing an operation in the research platform."""

    def __init__(
        self,
        name: str,
        *,
        span_context: Optional[IntegrationSpanContext] = None,
        parent: Optional[IntegrationSpan] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        trace_id = uuid4().hex[:32]
        span_id = uuid4().hex[:16]

        if parent is not None:
            trace_id = parent.context.trace_id
            self._context = IntegrationSpanContext(trace_id, span_id, parent_span_id=parent.context.span_id)
        elif span_context is not None:
            self._context = span_context
        else:
            self._context = IntegrationSpanContext(trace_id, span_id)

        self._name: str = name
        self._attributes: Dict[str, Any] = attributes or {}
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._events: List[Dict[str, Any]] = []
        self._status: str = "unset"
        self._parent: Optional[IntegrationSpan] = parent

    @property
    def context(self) -> IntegrationSpanContext:
        return self._context

    @property
    def name(self) -> str:
        return self._name

    @property
    def duration_ms(self) -> float:
        if self._start_time is not None and self._end_time is not None:
            return (self._end_time - self._start_time) * 1000
        return 0.0

    def start(self) -> None:
        """Start the span."""
        self._start_time = time.monotonic()
        self._status = "running"

    def end(self, status: str = "ok") -> None:
        """End the span."""
        self._end_time = time.monotonic()
        self._status = status

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self._events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self._attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Export span as dictionary."""
        return {
            "trace_id": self._context.trace_id,
            "span_id": self._context.span_id,
            "parent_span_id": self._context.parent_span_id,
            "name": self._name,
            "status": self._status,
            "duration_ms": self.duration_ms,
            "attributes": self._attributes,
            "events": self._events,
            "start_time": self._start_time,
            "end_time": self._end_time,
        }


class IntegrationTracer:
    """Distributed tracer for the unified research platform.

    Manages trace creation, span lifecycle, and context propagation
    across all integration adapters.

    Usage::

        tracer = IntegrationTracer()
        with tracer.start_span("platform.initialize") as span:
            span.set_attribute("adapter_count", 14)
            # ... initialization logic ...
    """

    def __init__(self, *, tracer_id: Optional[str] = None) -> None:
        self._id: str = tracer_id or f"tracer-{uuid4().hex[:12]}"
        self._active_spans: Dict[str, IntegrationSpan] = {}
        self._completed_spans: List[Dict[str, Any]] = []
        self._max_history: int = 10000

    @property
    def id(self) -> str:
        return self._id

    # ------------------------------------------------------------------
    # Span Management
    # ------------------------------------------------------------------

    def start_span(
        self,
        name: str,
        *,
        parent: Optional[IntegrationSpan] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> IntegrationSpan:
        """Start a new trace span.

        Args:
            name: Span name (e.g., "experiment.run").
            parent: Optional parent span for nesting.
            attributes: Optional span attributes.

        Returns:
            A new IntegrationSpan.
        """
        span = IntegrationSpan(name=name, parent=parent, attributes=attributes)
        span.start()
        self._active_spans[span.context.span_id] = span
        logger.debug("Span started: %s [%s]", name, span.context.span_id)
        return span

    def end_span(self, span: IntegrationSpan, status: str = "ok") -> None:
        """End a trace span.

        Args:
            span: The span to end.
            status: Final status (ok, error).
        """
        span.end(status=status)
        self._active_spans.pop(span.context.span_id, None)
        self._completed_spans.append(span.to_dict())

        # Trim history
        if len(self._completed_spans) > self._max_history:
            self._completed_spans = self._completed_spans[-self._max_history:]

        logger.debug("Span ended: %s [%s] %.2fms", span.name, span.context.span_id, span.duration_ms)

    # ------------------------------------------------------------------
    # Context Management
    # ------------------------------------------------------------------

    def get_current_span(self) -> Optional[IntegrationSpan]:
        """Get the current span from context."""
        return _current_span.get()

    def set_current_span(self, span: IntegrationSpan) -> None:
        """Set the current span in context."""
        _current_span.set(span)

    # ------------------------------------------------------------------
    # Trace Decorator
    # ------------------------------------------------------------------

    def trace(self, name: Optional[str] = None):
        """Decorator to automatically trace async function calls.

        Usage::

            tracer = IntegrationTracer()

            @tracer.trace("portfolio.optimize")
            async def optimize_portfolio(portfolio_id):
                ...
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                span_name = name or f"{func.__module__}.{func.__qualname__}"
                span = self.start_span(span_name)
                self.set_current_span(span)
                try:
                    result = await func(*args, **kwargs)
                    self.end_span(span, "ok")
                    return result
                except Exception as exc:
                    span.set_attribute("error", str(exc))
                    span.add_event("exception", {"type": type(exc).__name__, "message": str(exc)})
                    self.end_span(span, "error")
                    raise
            return wrapper
        return decorator

    # ------------------------------------------------------------------
    # Timeline Generation
    # ------------------------------------------------------------------

    def get_timeline(
        self,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get trace timeline for visualization.

        Args:
            trace_id: Optional trace ID to filter by.

        Returns:
            List of span records sorted by start time.
        """
        spans = self._completed_spans
        if trace_id is not None:
            spans = [s for s in spans if s["trace_id"] == trace_id]
        return sorted(spans, key=lambda s: s.get("start_time", 0))

    def get_active_spans(self) -> List[Dict[str, Any]]:
        """Get currently active spans."""
        return [s.to_dict() for s in self._active_spans.values()]

    def get_summary(self) -> Dict[str, Any]:
        """Get tracer summary."""
        return {
            "tracer_id": self._id,
            "active_spans": len(self._active_spans),
            "completed_spans": len(self._completed_spans),
            "recent_spans": self._completed_spans[-5:] if self._completed_spans else [],
        }

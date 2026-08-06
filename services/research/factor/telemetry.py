"""Factor Telemetry — distributed tracing for factor research operations.

Unified tracing::

    Factor Engine → Tracing → Metrics → Research Timeline → Audit
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
    """Span kind classification."""

    INTERNAL = "internal"
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    """Span status codes."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class FactorSpanContext:
    """Immutable span context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    is_remote: bool = False
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class FactorSpan:
    """A single trace span for factor operations."""

    name: str
    context: FactorSpanContext
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self, status: SpanStatus = SpanStatus.OK) -> None:
        self.status = status
        self.end_time = time.time()

    def finish_with_error(self, error: Exception) -> None:
        self.status = SpanStatus.ERROR
        self.error_message = str(error)
        self.end_time = time.time()
        self.add_event("exception", {"message": str(error), "type": type(error).__name__})


class FactorTracer:
    """Distributed tracer for factor research operations.

    Provides:
    * Span creation and management
    * Context propagation across async boundaries
    * Timeline reconstruction for research audits
    * Performance profiling
    """

    def __init__(self, service_name: str = "icyquant-factor") -> None:
        self._service_name = service_name
        self._active_spans: Dict[str, FactorSpan] = {}
        self._completed_spans: List[FactorSpan] = []
        self._lock = asyncio.Lock()
        self._max_completed = 10000

    @property
    def service_name(self) -> str:
        return self._service_name

    def start_span(
        self,
        name: str,
        parent_context: Optional[FactorSpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> FactorSpan:
        """Start a new trace span.

        Args:
            name: span operation name
            parent_context: parent span context for propagation
            kind: span kind
            attributes: initial span attributes

        Returns:
            new FactorSpan
        """
        trace_id = parent_context.trace_id if parent_context else str(uuid4())
        span_id = str(uuid4())
        parent_span_id = parent_context.span_id if parent_context else None

        context = FactorSpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )

        span = FactorSpan(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {},
        )

        span.set_attribute("service.name", self._service_name)
        span.set_attribute("timestamp", datetime.now(timezone.utc).isoformat())

        self._active_spans[span_id] = span

        logger.debug("Span started: %s (trace=%s, span=%s)", name, trace_id[:8], span_id[:8])
        return span

    def end_span(self, span: FactorSpan) -> None:
        """End a trace span."""
        span.finish()

        self._active_spans.pop(span.context.span_id, None)
        self._completed_spans.append(span)

        if len(self._completed_spans) > self._max_completed:
            self._completed_spans = self._completed_spans[-self._max_completed:]

        logger.debug(
            "Span ended: %s (duration=%.2fms, status=%s)",
            span.name, span.duration_ms, span.status.value,
        )

    @contextmanager
    def trace(self, name: str, **attributes):
        """Context manager for tracing a block of code.

        Usage::

            with tracer.trace("compute_factor", factor_name="momentum_20d") as span:
                result = compute()
                span.set_attribute("result_count", len(result))
        """
        span = self.start_span(name, attributes=attributes)
        try:
            yield span
            span.finish(SpanStatus.OK)
        except Exception as exc:
            span.finish_with_error(exc)
            raise
        finally:
            self._active_spans.pop(span.context.span_id, None)
            self._completed_spans.append(span)

    def trace_async(self, name: str):
        """Decorator for tracing async functions.

        Usage::

            @tracer.trace_async("calculate_factor")
            async def calculate(factor_name: str):
                ...
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                span = self.start_span(name, attributes={
                    "function": func.__name__,
                })
                try:
                    result = await func(*args, **kwargs)
                    span.finish(SpanStatus.OK)
                    return result
                except Exception as exc:
                    span.finish_with_error(exc)
                    raise
                finally:
                    self._active_spans.pop(span.context.span_id, None)
                    self._completed_spans.append(span)
            return wrapper
        return decorator

    def get_trace(self, trace_id: str) -> List[FactorSpan]:
        """Retrieve all spans for a given trace."""
        return [s for s in self._completed_spans if s.context.trace_id == trace_id]

    def timeline(self) -> List[Dict[str, Any]]:
        """Generate research timeline from completed spans."""
        sorted_spans = sorted(self._completed_spans, key=lambda s: s.start_time)
        return [
            {
                "name": s.name,
                "trace_id": s.context.trace_id[:8],
                "span_id": s.context.span_id[:8],
                "parent_id": s.context.parent_span_id[:8] if s.context.parent_span_id else None,
                "start": s.start_time,
                "duration_ms": s.duration_ms,
                "status": s.status.value,
                "attributes": s.attributes,
            }
            for s in sorted_spans
        ]

    def stats(self) -> Dict[str, Any]:
        """Tracer statistics."""
        completed = len(self._completed_spans)
        errors = sum(1 for s in self._completed_spans if s.status == SpanStatus.ERROR)

        if completed > 0:
            avg_duration = sum(s.duration_ms for s in self._completed_spans) / completed
        else:
            avg_duration = 0.0

        return {
            "active_spans": len(self._active_spans),
            "completed_spans": completed,
            "error_spans": errors,
            "avg_duration_ms": avg_duration,
        }

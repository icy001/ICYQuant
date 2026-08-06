"""Portfolio Telemetry — distributed tracing for portfolio research.

Unified tracing::

    Portfolio Engine → Tracing → Metrics → Optimization Timeline
    → Risk Timeline → Audit
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


class SpanStatus(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class PortfolioSpanContext:
    """Span context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    is_remote: bool = False
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class PortfolioSpan:
    """A single trace span in portfolio research."""

    name: str
    context: PortfolioSpanContext
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.monotonic() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.monotonic(),
            "attributes": attributes or {},
        })

    def set_error(self, message: str) -> None:
        self.status = SpanStatus.ERROR
        self.error_message = message

    def finish(self) -> None:
        self.end_time = time.monotonic()
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


class PortfolioTracer:
    """Distributed tracing for portfolio research.

    Manages span lifecycle and context propagation across
    portfolio construction, optimization, and analysis operations.
    """

    def __init__(self) -> None:
        self._spans: Dict[str, PortfolioSpan] = {}
        self._active_spans: Dict[str, PortfolioSpan] = {}
        self._exported_spans: List[Dict[str, Any]] = []
        self._enabled: bool = True

    def start_span(
        self,
        name: str,
        parent_context: Optional[PortfolioSpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PortfolioSpan:
        """Start a new span."""

        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        else:
            trace_id = str(uuid4())
            parent_span_id = None

        context = PortfolioSpanContext(
            trace_id=trace_id,
            span_id=str(uuid4()),
            parent_span_id=parent_span_id,
        )

        span = PortfolioSpan(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {},
        )

        self._spans[context.span_id] = span
        self._active_spans[context.span_id] = span

        return span

    def end_span(self, span: PortfolioSpan) -> None:
        span.finish()
        self._active_spans.pop(span.context.span_id, None)
        self._exported_spans.append(span.to_dict())

    @contextmanager
    def span(
        self,
        name: str,
        parent_context: Optional[PortfolioSpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for automatic span lifecycle."""
        span = self.start_span(
            name=name,
            parent_context=parent_context,
            kind=kind,
            attributes=attributes,
        )
        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            self.end_span(span)

    def trace(self, name: Optional[str] = None):
        """Decorator for tracing portfolio operations."""

        def decorator(func: Callable) -> Callable:
            span_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.span(span_name) as span:
                    span.attributes["function"] = func.__name__
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def get_active_spans(self) -> Dict[str, PortfolioSpan]:
        return dict(self._active_spans)

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a trace."""
        return [
            s.to_dict() for s in self._spans.values()
            if s.context.trace_id == trace_id
        ]

    def export(self) -> List[Dict[str, Any]]:
        """Export all completed spans."""
        return list(self._exported_spans)

    def clear(self) -> None:
        self._spans.clear()
        self._active_spans.clear()
        self._exported_spans.clear()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

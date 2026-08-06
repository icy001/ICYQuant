"""Research Telemetry — OpenTelemetry tracing and distributed context propagation.

Provides distributed tracing, span management, and context propagation
across the research platform for observability and debugging.
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
    """OpenTelemetry-compatible span kinds."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class TraceStatus(str, Enum):
    """Span/trace status codes."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanContext:
    """Immutable span context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    is_remote: bool = False
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class SpanAttributes:
    """Key-value attributes attached to a span."""

    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, str]] = field(default_factory=list)

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def add_link(self, trace_id: str, span_id: str) -> None:
        self.links.append({"trace_id": trace_id, "span_id": span_id})


@dataclass
class TraceSpan:
    """A single span in a distributed trace.

    Represents a unit of work with timing, attributes, and status.
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    kind: SpanKind = SpanKind.INTERNAL
    status: TraceStatus = TraceStatus.UNSET
    status_message: str = ""
    start_time: float = 0.0
    end_time: Optional[float] = None
    attributes: SpanAttributes = field(default_factory=SpanAttributes)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start_time == 0.0:
            self.start_time = time.monotonic()

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.monotonic()
        return (end - self.start_time) * 1000

    def finish(self, status: TraceStatus = TraceStatus.OK, message: str = "") -> None:
        self.end_time = time.monotonic()
        self.status = status
        self.status_message = message

    def fail(self, error: Exception) -> None:
        self.finish(TraceStatus.ERROR, str(error))
        self.attributes.set("error", True)
        self.attributes.set("error.type", type(error).__name__)
        self.attributes.set("error.message", str(error))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "status_message": self.status_message,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes.attributes,
            "events": self.attributes.events,
            "links": self.attributes.links,
        }

    def __repr__(self) -> str:
        return f"TraceSpan({self.name}, {self.duration_ms:.1f}ms, status={self.status.value})"


class ResearchTracer:
    """OpenTelemetry-compatible tracer for the research platform.

    Provides distributed tracing with automatic span creation,
    context propagation, and decorator-based instrumentation.

    Usage::

        tracer = ResearchTracer(service_name="research-platform")

        @tracer.trace("experiment.execute")
        async def execute_experiment(experiment_id: str):
            ...

        with tracer.start_span("data.load") as span:
            span.attributes.set("dataset_id", dataset_id)
            data = load_data(dataset_id)
            span.finish()
    """

    # Global counters
    _spans_created: int = 0
    _spans_completed: int = 0
    _spans_errored: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        service_name: str = "research-platform",
        service_version: str = "1.0.0",
        enabled: bool = True,
        sample_rate: float = 1.0,
    ) -> None:
        self._service_name = service_name
        self._service_version = service_version
        self._enabled = enabled
        self._sample_rate = sample_rate
        self._spans: Dict[str, TraceSpan] = {}
        self._current_context: Optional[SpanContext] = None
        self._exporters: List[Callable] = []

    # ---- Context Management ----

    def set_context(self, ctx: SpanContext) -> None:
        self._current_context = ctx

    def get_context(self) -> Optional[SpanContext]:
        return self._current_context

    def clear_context(self) -> None:
        self._current_context = None

    # ---- Span Creation ----

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[SpanContext] = None,
    ) -> TraceSpan:
        """Create and start a new span.

        Automatically links to the current context as parent.
        """
        if not self._enabled:
            return TraceSpan(name=name, trace_id="disabled", span_id="disabled")

        parent_ctx = parent or self._current_context
        trace_id = parent_ctx.trace_id if parent_ctx else str(uuid4())
        span_id = str(uuid4())

        span = TraceSpan(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_ctx.span_id if parent_ctx else None,
            kind=kind,
        )

        if attributes:
            for k, v in attributes.items():
                span.attributes.set(k, v)

        span.attributes.set("service.name", self._service_name)
        span.attributes.set("service.version", self._service_version)

        self._spans[span_id] = span
        self._current_context = SpanContext(
            trace_id=trace_id, span_id=span_id,
            parent_span_id=parent_ctx.span_id if parent_ctx else None,
        )
        ResearchTracer._spans_created += 1
        return span

    def end_span(self, span: TraceSpan, status: TraceStatus = TraceStatus.OK) -> None:
        """End a span and export it."""
        span.finish(status)
        if span.status == TraceStatus.ERROR:
            ResearchTracer._spans_errored += 1
        else:
            ResearchTracer._spans_completed += 1
        self._export(span)

    # ---- Decorator ----

    def trace(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        capture_args: bool = False,
    ) -> Callable:
        """Decorator to automatically trace a function call.

        Usage::

            @tracer.trace("dataset.load")
            async def load_dataset(dataset_id: str):
                ...
        """
        def decorator(func: Callable) -> Callable:
            span_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                span = self.start_span(span_name, kind=kind)
                if capture_args:
                    span.attributes.set("args", str(args[:5]))
                    span.attributes.set("kwargs", str(dict(list(kwargs.items())[:5])))
                try:
                    result = await func(*args, **kwargs)
                    self.end_span(span, TraceStatus.OK)
                    return result
                except Exception as exc:
                    span.fail(exc)
                    self.end_span(span, TraceStatus.ERROR)
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                span = self.start_span(span_name, kind=kind)
                if capture_args:
                    span.attributes.set("args", str(args[:5]))
                    span.attributes.set("kwargs", str(dict(list(kwargs.items())[:5])))
                try:
                    result = func(*args, **kwargs)
                    self.end_span(span, TraceStatus.OK)
                    return result
                except Exception as exc:
                    span.fail(exc)
                    self.end_span(span, TraceStatus.ERROR)
                    raise

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    @contextmanager
    def span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, **attrs: Any):
        """Context manager for manual span creation.

        Usage::

            with tracer.span("data.validation", dataset_id="ds-001") as span:
                validate_data()
        """
        span = self.start_span(name, kind=kind)
        for k, v in attrs.items():
            span.attributes.set(k, v)
        try:
            yield span
            self.end_span(span, TraceStatus.OK)
        except Exception as exc:
            span.fail(exc)
            self.end_span(span, TraceStatus.ERROR)
            raise

    # ---- Export ----

    def register_exporter(self, exporter: Callable[[TraceSpan], None]) -> None:
        """Register a span exporter (e.g., to console, OTLP, Jaeger)."""
        self._exporters.append(exporter)

    def _export(self, span: TraceSpan) -> None:
        for exporter in self._exporters:
            try:
                exporter(span.to_dict())
            except Exception:
                logger.debug("Span export failed", exc_info=True)

    # ---- Query ----

    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        return self._spans.get(span_id)

    def get_spans_by_trace_id(self, trace_id: str) -> List[TraceSpan]:
        return [s for s in self._spans.values() if s.trace_id == trace_id]

    # ---- Statistics ----

    @property
    def spans_created(self) -> int:
        return ResearchTracer._spans_created

    @property
    def spans_completed(self) -> int:
        return ResearchTracer._spans_completed

    @property
    def spans_errored(self) -> int:
        return ResearchTracer._spans_errored

    def stats(self) -> Dict[str, Any]:
        return {
            "service": self._service_name,
            "enabled": self._enabled,
            "sample_rate": self._sample_rate,
            "spans_created": ResearchTracer._spans_created,
            "spans_completed": ResearchTracer._spans_completed,
            "spans_errored": ResearchTracer._spans_errored,
            "active_context": self._current_context.trace_id if self._current_context else None,
        }

    def __repr__(self) -> str:
        return (
            f"ResearchTracer(service={self._service_name}, "
            f"spans={ResearchTracer._spans_created}, "
            f"enabled={self._enabled})"
        )

"""
Tracer.

The main entry point for creating spans
and managing trace context. Provides a
clean API for starting and finishing spans
within the current trace.

Usage:
    tracer = Tracer(manager=manager)

    # Start a span
    span = tracer.start_span("db_query")

    # ... do work ...

    # Finish the span
    tracer.finish_span(span)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .context import set_span
from .manager import TraceManager
from .models import SpanKind, SpanModel, SpanStatus, TraceModel
from .span import SpanFactory
from .trace import TraceFactory


class Tracer:
    """
    Distributed tracer.

    Creates and manages spans within traces,
    handling context propagation and parent-
    child relationships automatically.

    Features:
    - Automatic trace ID propagation
    - Parent span inheritance
    - Context management
    - Span lifecycle (start/finish)
    - Attribute and event support

    Usage:
        tracer = Tracer()

        # Root span
        with tracer.span("http_request") as span:
            span.set_attr("method", "GET")
            # ... process request ...
    """

    def __init__(
        self,
        manager: Optional[TraceManager] = None,
        span_factory: Optional[SpanFactory] = None,
    ) -> None:
        """
        Initialize tracer.

        Args:
            manager: Optional TraceManager. Uses default if None.
            span_factory: Optional SpanFactory.
        """

        self._manager = manager or TraceManager()
        self._factory = span_factory or SpanFactory()

    @property
    def manager(
        self,
    ) -> TraceManager:
        """Get trace manager."""
        return self._manager

    def start_span(
        self,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[SpanModel] = None,
        trace: Optional[TraceModel] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SpanModel:
        """
        Start a new span.

        If no parent is provided, uses the
        current span as parent. If no trace
        is active, creates a new trace.

        Args:
            operation: Span operation name.
            kind: Span kind.
            parent: Optional explicit parent span.
            trace: Optional explicit trace.
            attributes: Optional initial attributes.

        Returns:
            New SpanModel (active).
        """

        # Determine parent
        parent_span = parent or self._manager.current_span()
        current_trace = trace or self._manager.current()

        # Create span
        span = self._factory.create(
            operation=operation,
            parent=parent_span,
            kind=kind,
        )

        # Set initial attributes
        if attributes:
            for k, v in attributes.items():
                span.add_attribute(k, v)

        # Create trace if none exists
        if current_trace is None:
            current_trace = TraceFactory.create(span)
            self._manager.set(current_trace)
        else:
            current_trace.add_span(span.span_id)

        # Set as current span
        self._manager.set_span(span)

        return span

    def finish_span(
        self,
        span: SpanModel,
        status: SpanStatus = SpanStatus.OK,
        end_time: Optional[datetime] = None,
    ) -> SpanModel:
        """
        Finish a span.

        Args:
            span: Span to finish.
            status: Final span status.
            end_time: Optional explicit end time.

        Returns:
            Finished SpanModel.
        """

        span.set_status(status)
        span.finish(end_time=end_time)

        # Restore parent as current span
        parent_id = span.parent_span_id
        if parent_id is not None:
            # Find parent span in trace
            # For simplicity, just clear current span
            # In production, would look up parent
            pass

        return span

    def span(
        self,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "SpanContextManager":
        """
        Create a context-managed span.

        Usage:
            with tracer.span("operation") as span:
                span.set_attr("key", "value")
                # ... do work ...
        # Span automatically finished

        Args:
            operation: Span operation name.
            kind: Span kind.
            attributes: Optional initial attributes.

        Returns:
            SpanContextManager instance.
        """

        return SpanContextManager(
            tracer=self,
            operation=operation,
            kind=kind,
            attributes=attributes,
        )


class SpanContextManager:
    """
    Span context manager.

    Provides a context manager interface
    for spans, automatically finishing
    the span on exit and restoring the
    parent span context.

    Usage:
        with tracer.span("op") as span:
            span.add_attribute("key", "value")
    """

    def __init__(
        self,
        tracer: Tracer,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize context manager."""

        self._tracer = tracer
        self._operation = operation
        self._kind = kind
        self._attributes = attributes
        self._span: Optional[SpanModel] = None
        self._previous_span: Optional[SpanModel] = None

    def __enter__(
        self,
    ) -> SpanModel:
        """Enter span context."""

        self._previous_span = self._tracer.manager.current_span()
        self._span = self._tracer.start_span(
            operation=self._operation,
            kind=self._kind,
            attributes=self._attributes,
        )
        return self._span

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:
        """Exit span context."""

        if self._span is not None:
            status = SpanStatus.OK
            if exc_type is not None:
                status = SpanStatus.ERROR
                self._span.add_event(
                    "exception",
                    {
                        "type": str(exc_type),
                        "message": str(exc_val),
                    },
                )
            self._tracer.finish_span(self._span, status=status)

        # Restore previous span
        if self._previous_span is not None:
            self._tracer.manager.set_span(self._previous_span)
        else:
            # Clear span context
            from .context import span_context
            span_context.set(None)

"""
Trace context.

Provides contextvar-based trace context
propagation across async tasks, ensuring
the current trace and span are accessible
anywhere within a request scope.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from .models import SpanModel, TraceModel

# Current trace context
trace_context: ContextVar[Optional[TraceModel]] = ContextVar(
    "trace_context",
    default=None,
)

# Current span context
span_context: ContextVar[Optional[SpanModel]] = ContextVar(
    "span_context",
    default=None,
)


def current_trace() -> Optional[TraceModel]:
    """Get the current trace."""

    return trace_context.get()


def current_span() -> Optional[SpanModel]:
    """Get the current span."""

    return span_context.get()


def set_trace(
    trace: Optional[TraceModel],
) -> None:
    """Set the current trace."""

    trace_context.set(trace)


def set_span(
    span: Optional[SpanModel],
) -> None:
    """Set the current span."""

    span_context.set(span)


def clear_trace() -> None:
    """Clear the current trace context."""

    trace_context.set(None)
    span_context.set(None)

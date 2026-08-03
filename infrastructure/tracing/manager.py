"""
Trace manager.

Manages the current trace context using
contextvars, providing a clean API for
getting, setting, and clearing the
active trace.
"""

from __future__ import annotations

from typing import Optional

from .context import clear_trace, current_span, current_trace, set_span, set_trace
from .models import SpanModel, TraceModel


class TraceManager:
    """
    Trace context manager.

    Provides centralized management of the
    current trace and span context.

    Usage:
        manager = TraceManager()
        trace = manager.current()
        manager.set(my_trace)
        manager.clear()
    """

    @staticmethod
    def current() -> Optional[TraceModel]:
        """Get the current trace."""
        return current_trace()

    @staticmethod
    def current_span() -> Optional[SpanModel]:
        """Get the current span."""
        return current_span()

    @staticmethod
    def set(
        trace: TraceModel,
    ) -> None:
        """Set the current trace."""
        set_trace(trace)

    @staticmethod
    def set_span(
        span: SpanModel,
    ) -> None:
        """Set the current span."""
        set_span(span)

    @staticmethod
    def clear() -> None:
        """Clear the current trace context."""
        clear_trace()

    @staticmethod
    def trace_id() -> Optional[str]:
        """Get the current trace ID."""
        trace = current_trace()
        return trace.trace_id if trace else None

    @staticmethod
    def span_id() -> Optional[str]:
        """Get the current span ID."""
        span = current_span()
        return span.span_id if span else None

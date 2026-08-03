"""
Trace factory and model.

Defines the TraceModel dataclass and
TraceFactory for creating traces with
root spans.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from .models import SpanModel, TraceModel


class TraceFactory:
    """
    Trace factory.

    Creates TraceModel instances from
    root spans, establishing the trace
    hierarchy.

    Usage:
        factory = TraceFactory()
        trace = factory.create(root_span)
        trace.add_span(child_span.span_id)
    """

    @staticmethod
    def create(
        root_span: SpanModel,
        trace_id: Optional[str] = None,
        sampled: bool = True,
    ) -> TraceModel:
        """
        Create a new trace from a root span.

        Args:
            root_span: The root span.
            trace_id: Optional explicit trace ID.
            sampled: Whether the trace is sampled.

        Returns:
            New TraceModel.
        """

        tid = trace_id or root_span.trace_id

        trace = TraceModel(
            trace_id=tid,
            root_span_id=root_span.span_id,
            sampled=sampled,
            start_time=root_span.start_time,
        )
        trace.add_span(root_span.span_id)
        return trace

    @staticmethod
    def create_new(
        operation: str,
        sampled: bool = True,
    ) -> tuple:
        """
        Create a new trace with root span.

        Args:
            operation: Root span operation name.
            sampled: Whether the trace is sampled.

        Returns:
            Tuple of (TraceModel, root SpanModel).
        """

        from .span import SpanFactory

        root_span = SpanFactory.create_root(operation)
        trace = TraceFactory.create(root_span, sampled=sampled)
        return trace, root_span

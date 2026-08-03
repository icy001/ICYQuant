"""
Span factory.

Creates SpanModel instances with proper
trace ID propagation and parent-child
relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from .models import SpanKind, SpanModel


class SpanFactory:
    """
    Span factory.

    Creates spans with automatic trace ID
    propagation from parent spans and
    unique span ID generation.

    Usage:
        factory = SpanFactory()

        # Root span (new trace)
        root = factory.create("http_request")

        # Child span (inherits trace ID)
        child = factory.create("db_query", parent=root)
    """

    @staticmethod
    def create(
        operation: str,
        parent: Optional[SpanModel] = None,
        trace_id: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> SpanModel:
        """
        Create a new span.

        If parent is provided, the new span
        inherits the parent's trace_id and
        uses the parent's span_id as its
        parent_span_id.

        Args:
            operation: Span operation name.
            parent: Optional parent span.
            trace_id: Optional explicit trace ID.
            kind: Span kind.

        Returns:
            New SpanModel instance.
        """

        if parent is not None:
            tid = parent.trace_id
            parent_id = parent.span_id
        else:
            tid = trace_id or uuid.uuid4().hex
            parent_id = None

        return SpanModel(
            trace_id=tid,
            span_id=uuid.uuid4().hex,
            parent_span_id=parent_id,
            operation=operation,
            start_time=datetime.utcnow(),
            kind=kind,
        )

    @staticmethod
    def create_root(
        operation: str,
        trace_id: Optional[str] = None,
        kind: SpanKind = SpanKind.SERVER,
    ) -> SpanModel:
        """
        Create a root span (new trace).

        Args:
            operation: Span operation name.
            trace_id: Optional explicit trace ID.
            kind: Span kind (default: server).

        Returns:
            New root SpanModel.
        """

        return SpanModel(
            trace_id=trace_id or uuid.uuid4().hex,
            span_id=uuid.uuid4().hex,
            parent_span_id=None,
            operation=operation,
            start_time=datetime.utcnow(),
            kind=kind,
        )

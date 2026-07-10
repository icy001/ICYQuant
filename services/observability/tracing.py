"""
OpenTelemetry tracing service.
"""

from __future__ import annotations

from dataclasses import dataclass

from uuid import uuid4

from contextlib import contextmanager


@dataclass(
    frozen=True,
)
class SpanContext:
    trace_id: str
    span_id: str
    parent_id: str | None = None


class Tracer:
    def __init__(
        self,
        service_name: str,
    ):
        self.service_name = service_name

    def create_span(
        self,
        operation: str,
        parent: SpanContext | None = None,
    ) -> SpanContext:
        return SpanContext(
            trace_id=(
                parent.trace_id
                if parent
                else uuid4().hex
            ),
            span_id=uuid4().hex[:16],
            parent_id=(
                parent.span_id
                if parent
                else None
            ),
        )

    @contextmanager
    def span(
        self,
        operation: str,
        parent=None,
    ):
        context = self.create_span(
            operation,
            parent,
        )
        try:
            yield context
        finally:
            pass
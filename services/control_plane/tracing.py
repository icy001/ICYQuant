"""Distributed tracing for control commands (Commit 29 Part 1.5 §29-32).

One command produces a trace:

    control.command
      ├── control.idempotency
      ├── control.governance
      ├── control.authorization
      ├── control.dispatch
      ├── control.execution
      └── control.recovery / control.reconciliation

Trace attributes are redacted through ``diagnostics.redact`` so sensitive
parameters (credentials, tokens, ...) are never recorded (§31-32).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .diagnostics import redact


@dataclass
class TraceSpan:
    """A single span inside a command trace (§30)."""

    span_id: str
    trace_id: str
    name: str
    parent_span_id: str | None
    started_at: datetime
    attributes: dict[str, Any] = field(default_factory=dict)
    ended_at: datetime | None = None

    def finish(self, ended_at: datetime | None = None) -> "TraceSpan":
        self.ended_at = ended_at or datetime.now(timezone.utc)
        return self

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class ControlTrace:
    """In-memory trace collector with redacted attributes (§29-31).

    Span IDs are deterministic (monotonic) for testability; a production
    adapter would map onto OpenTelemetry or similar.
    """

    def __init__(self) -> None:
        self._spans: list[TraceSpan] = []
        self._sequence = 0

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
        parent: TraceSpan | None = None,
        started_at: datetime | None = None,
    ) -> TraceSpan:
        self._sequence += 1
        if trace_id is None:
            trace_id = parent.trace_id if parent is not None else f"TRACE-{self._sequence:04d}"
        span = TraceSpan(
            span_id=f"SPAN-{self._sequence:04d}",
            trace_id=trace_id,
            name=name,
            parent_span_id=parent.span_id if parent else None,
            started_at=started_at or datetime.now(timezone.utc),
            attributes=redact(attributes or {}),
        )
        self._spans.append(span)
        return span

    def end_span(self, span: TraceSpan, ended_at: datetime | None = None) -> TraceSpan:
        return span.finish(ended_at)

    def spans(self, trace_id: str | None = None) -> tuple[TraceSpan, ...]:
        if trace_id is None:
            return tuple(self._spans)
        return tuple(span for span in self._spans if span.trace_id == trace_id)

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "span_id": span.span_id,
                "trace_id": span.trace_id,
                "name": span.name,
                "parent_span_id": span.parent_span_id,
                "started_at": span.started_at.isoformat(),
                "ended_at": span.ended_at.isoformat() if span.ended_at else None,
                "attributes": dict(span.attributes),
            }
            for span in self._spans
        ]

"""
ICYQuant AI Research Telemetry — distributed tracing for research workflows.

Provides end-to-end tracing across the research pipeline: Research Timeline,
Retrieval Timeline, Reasoning Timeline, Report Timeline, and Approval Timeline.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


class TraceKind(str, Enum):
    RESEARCH = "research"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    REPORT = "report"
    APPROVAL = "approval"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class Span:
    """A single span in a trace."""
    span_id: str
    trace_id: str
    parent_span_id: str = ""
    name: str = ""
    kind: TraceKind = TraceKind.RESEARCH
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000


@dataclass
class Trace:
    """A complete trace of a research operation."""
    trace_id: str
    kind: TraceKind
    spans: list[Span] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchTelemetry:
    """Distributed tracing for AI research workflows.

    Trace types:
        - Research Timeline:   Full research request lifecycle
        - Retrieval Timeline:  Knowledge retrieval operations
        - Reasoning Timeline:  Hypothesis generation & reasoning
        - Report Timeline:     Report generation process
        - Approval Timeline:   Review & approval workflow
    """

    def __init__(self) -> None:
        self._traces: dict[str, Trace] = {}
        self._active_spans: dict[str, Span] = {}
        self._total_traces = 0

    @contextmanager
    def trace(self, name: str, kind: TraceKind = TraceKind.RESEARCH) -> Generator[Span, None, None]:
        """Create a traced context for an operation."""
        trace_id = str(uuid.uuid4())
        span = Span(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            name=name,
            kind=kind,
        )

        trace = Trace(trace_id=trace_id, kind=kind)
        trace.spans.append(span)
        self._traces[trace_id] = trace
        self._active_spans[span.span_id] = span
        self._total_traces += 1

        try:
            yield span
            span.status = SpanStatus.OK
        except Exception:
            span.status = SpanStatus.ERROR
            raise
        finally:
            span.end_time = time.time()
            self._active_spans.pop(span.span_id, None)

    def start_span(
        self,
        name: str,
        trace_id: str,
        kind: TraceKind = TraceKind.RESEARCH,
        parent_span_id: str = "",
    ) -> Span:
        """Start a child span within an existing trace."""
        span = Span(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
        )

        if trace_id in self._traces:
            self._traces[trace_id].spans.append(span)

        self._active_spans[span.span_id] = span
        return span

    def end_span(self, span_id: str, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span."""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end_time = time.time()
            span.status = status

    def add_event(self, span_id: str, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to a span."""
        span = self._active_spans.get(span_id)
        if span:
            span.events.append({
                "name": name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            })

    def set_attribute(self, span_id: str, key: str, value: Any) -> None:
        """Set an attribute on a span."""
        span = self._active_spans.get(span_id)
        if span:
            span.attributes[key] = value

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get the most recent traces."""
        recent = list(self._traces.values())[-limit:]
        return [
            {
                "trace_id": t.trace_id,
                "kind": t.kind.value,
                "span_count": len(t.spans),
                "duration_ms": sum(s.duration_ms for s in t.spans),
                "status": "error" if any(s.status == SpanStatus.ERROR for s in t.spans) else "ok",
                "started_at": t.started_at.isoformat(),
            }
            for t in recent
        ]

    @property
    def active_span_count(self) -> int:
        return len(self._active_spans)

    @property
    def total_traces(self) -> int:
        return self._total_traces

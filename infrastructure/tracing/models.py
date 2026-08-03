"""
Tracing data models.

Defines the core data structures for
distributed tracing: SpanModel, TraceModel,
SpanEvent, and SpanStatus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SpanKind(str, Enum):
    """Span kind."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    """Span status."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """
    A span event.

    Represents a timestamped event within
    a span, such as a log entry or exception.

    Attributes:
        name: Event name.
        timestamp: When the event occurred.
        attributes: Event attributes.
    """

    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanModel:
    """
    A span model.

    Represents a unit of work within a trace,
    with timing, attributes, events, and
    parent-child relationships.

    Attributes:
        trace_id: Trace identifier.
        span_id: Unique span identifier.
        parent_span_id: Parent span ID (None for root).
        operation: Span operation name.
        kind: Span kind (internal, server, client, etc.).
        start_time: Span start timestamp.
        end_time: Span end timestamp (None if active).
        status: Span status.
        attributes: Span attributes.
        events: Span events.
    """

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    start_time: datetime
    kind: SpanKind = SpanKind.INTERNAL
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)

    @property
    def is_active(
        self,
    ) -> bool:
        """Check if span is still active."""

        return self.end_time is None

    @property
    def duration_ms(
        self,
    ) -> float:
        """
        Get span duration in milliseconds.

        Returns 0 if span is still active.
        """

        if self.end_time is None:
            return 0.0
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def add_attribute(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Add an attribute."""

        self.attributes[key] = value

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SpanEvent:
        """Add an event."""

        event = SpanEvent(
            name=name,
            timestamp=datetime.utcnow(),
            attributes=attributes or {},
        )
        self.events.append(event)
        return event

    def set_status(
        self,
        status: SpanStatus,
    ) -> None:
        """Set span status."""

        self.status = status

    def finish(
        self,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Finish the span."""

        self.end_time = end_time or datetime.utcnow()

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""

        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [
                {
                    "name": e.name,
                    "timestamp": e.timestamp.isoformat(),
                    "attributes": e.attributes,
                }
                for e in self.events
            ],
        }


@dataclass
class TraceModel:
    """
    A trace model.

    Represents a complete distributed trace
    containing multiple spans.

    Attributes:
        trace_id: Unique trace identifier.
        root_span_id: Root span identifier.
        spans: List of span IDs in the trace.
        sampled: Whether the trace was sampled.
        start_time: Trace start time.
        end_time: Trace end time (None if active).
    """

    trace_id: str
    root_span_id: str
    spans: List[str] = field(default_factory=list)
    sampled: bool = True
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    @property
    def span_count(
        self,
    ) -> int:
        """Get span count."""
        return len(self.spans)

    @property
    def is_active(
        self,
    ) -> bool:
        """Check if trace is still active."""
        return self.end_time is None

    @property
    def duration_ms(
        self,
    ) -> float:
        """Get trace duration in milliseconds."""

        end = self.end_time or datetime.utcnow()
        delta = end - self.start_time
        return delta.total_seconds() * 1000

    def add_span(
        self,
        span_id: str,
    ) -> None:
        """Add a span to the trace."""

        if span_id not in self.spans:
            self.spans.append(span_id)

    def finish(
        self,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Finish the trace."""

        self.end_time = end_time or datetime.utcnow()

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""

        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "span_count": self.span_count,
            "sampled": self.sampled,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "spans": self.spans,
        }

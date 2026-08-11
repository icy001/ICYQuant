"""Lifecycle Telemetry — Distributed tracing and timeline tracking.

Provides telemetry for order lifecycle operations, including:
- Lifecycle Timeline: Full order journey tracking
- Transition Timeline: State change timings
- Fill Timeline: Execution trace
- Replay Timeline: Recovery event tracing
- Audit Timeline: Compliance audit trace
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """Telemetry span type."""
    LIFECYCLE = "lifecycle"
    TRANSITION = "transition"
    FILL = "fill"
    REPLAY = "replay"
    AUDIT = "audit"


@dataclass
class TelemetrySpan:
    """A single telemetry span representing an operation."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    kind: SpanKind
    name: str
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    status: str = "running"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Span duration in milliseconds."""
        if self.end_time is None:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000
        return (self.end_time - self.start_time).total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "ok") -> None:
        """Mark span as finished."""
        self.end_time = datetime.now(timezone.utc)
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class LifecycleTelemetry:
    """Telemetry provider for order lifecycle operations.

    Creates distributed traces and spans for lifecycle events,
    enabling timeline visualization and performance analysis.

    Usage::

        telemetry = LifecycleTelemetry()
        span = telemetry.start_lifecycle_span(order_id)
        # ... do work ...
        span.add_event("validated")
        span.finish()
    """

    def __init__(self) -> None:
        # trace_id → list of spans
        self._traces: dict[str, list[TelemetrySpan]] = defaultdict(list)
        # order_id → current trace_id
        self._active_traces: dict[str, str] = {}

    # ---- Lifecycle Timeline ----

    def start_lifecycle_span(
        self,
        order_id: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Start a new lifecycle span for an order.

        Args:
            order_id: Order identifier
            attributes: Additional span attributes

        Returns:
            A new TelemetrySpan
        """
        trace_id = str(uuid.uuid4())
        self._active_traces[order_id] = trace_id

        span = TelemetrySpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=None,
            kind=SpanKind.LIFECYCLE,
            name=f"order_lifecycle:{order_id}",
            attributes=attributes or {"order_id": order_id},
        )
        self._traces[trace_id].append(span)
        return span

    # ---- Transition Timeline ----

    def start_transition_span(
        self,
        order_id: str,
        from_status: str,
        to_status: str,
    ) -> Optional[TelemetrySpan]:
        """Start a transition span for a state change.

        Args:
            order_id: Order identifier
            from_status: Current status
            to_status: Target status

        Returns:
            Transition span or None if no active trace
        """
        trace_id = self._active_traces.get(order_id)
        if trace_id is None:
            return None

        parent_span = self._get_active_span(trace_id)
        span = TelemetrySpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            kind=SpanKind.TRANSITION,
            name=f"transition:{from_status}->{to_status}",
            attributes={
                "order_id": order_id,
                "from_status": from_status,
                "to_status": to_status,
            },
        )
        self._traces[trace_id].append(span)
        return span

    # ---- Fill Timeline ----

    def start_fill_span(
        self,
        order_id: str,
        fill_qty: float,
        fill_price: float,
    ) -> Optional[TelemetrySpan]:
        """Start a fill span for a trade execution.

        Args:
            order_id: Order identifier
            fill_qty: Fill quantity
            fill_price: Fill price

        Returns:
            Fill span or None if no active trace
        """
        trace_id = self._active_traces.get(order_id)
        if trace_id is None:
            return None

        parent_span = self._get_active_span(trace_id)
        span = TelemetrySpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            kind=SpanKind.FILL,
            name=f"fill:{order_id}",
            attributes={
                "order_id": order_id,
                "fill_quantity": fill_qty,
                "fill_price": fill_price,
            },
        )
        self._traces[trace_id].append(span)
        return span

    # ---- Replay Timeline ----

    def start_replay_span(
        self,
        order_id: str,
        event_count: int = 0,
    ) -> Optional[TelemetrySpan]:
        """Start a replay span for event recovery.

        Args:
            order_id: Order identifier
            event_count: Number of events being replayed

        Returns:
            Replay span or None if no active trace
        """
        trace_id = self._active_traces.get(order_id)
        if trace_id is None:
            return None

        parent_span = self._get_active_span(trace_id)
        span = TelemetrySpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            kind=SpanKind.REPLAY,
            name=f"replay:{order_id}",
            attributes={
                "order_id": order_id,
                "event_count": event_count,
            },
        )
        self._traces[trace_id].append(span)
        return span

    # ---- Audit Timeline ----

    def start_audit_span(
        self,
        order_id: str,
        action: str,
    ) -> Optional[TelemetrySpan]:
        """Start an audit span.

        Args:
            order_id: Order identifier
            action: Audit action

        Returns:
            Audit span or None if no active trace
        """
        trace_id = self._active_traces.get(order_id)
        if trace_id is None:
            return None

        parent_span = self._get_active_span(trace_id)
        span = TelemetrySpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            kind=SpanKind.AUDIT,
            name=f"audit:{action}",
            attributes={
                "order_id": order_id,
                "action": action,
            },
        )
        self._traces[trace_id].append(span)
        return span

    # ---- Query ----

    def get_trace(self, trace_id: str) -> list[TelemetrySpan]:
        """Get all spans for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of spans in the trace
        """
        return sorted(
            self._traces.get(trace_id, []),
            key=lambda s: s.start_time,
        )

    def get_order_trace(self, order_id: str) -> list[TelemetrySpan]:
        """Get the trace for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of spans for the order
        """
        trace_id = self._active_traces.get(order_id)
        if trace_id is None:
            return []
        return self.get_trace(trace_id)

    def _get_active_span(self, trace_id: str) -> Optional[TelemetrySpan]:
        """Get the most recently created span in a trace."""
        spans = self._traces.get(trace_id, [])
        if not spans:
            return None
        return spans[-1]

    def to_dict(self) -> dict[str, Any]:
        """Serialize telemetry state."""
        return {
            "active_traces": len(self._active_traces),
            "total_spans": sum(len(s) for s in self._traces.values()),
        }

"""
Portfolio Decision Telemetry — Distributed tracing for the portfolio decision pipeline.

Part of Commit 13 Part 1.3: Portfolio Decision.

Spans:
    Sizing Timeline    — Position sizing evaluation path
    Allocation Timeline — Capital budget allocation path
    Decision Timeline   — Pipeline orchestration path
    Order Intent Timeline — Intent generation path (build → validate → route)
    Conflict Timeline   — Strategy conflict detection and resolution
    Netting Timeline    — Order netting and aggregation
    Audit Trail         — Full end-to-end trace for compliance

All spans are associated with a common trace_id for correlation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SpanKind(str, Enum):
    """Span kind classification."""
    SIZING = "sizing"
    ALLOCATION = "allocation"
    DECISION = "decision"
    ORDER_INTENT = "order_intent"
    CONFLICT = "conflict"
    NETTING = "netting"
    AUDIT = "audit"


class SpanStatus(str, Enum):
    """Span completion status."""
    OK = "OK"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class TelemetrySpan:
    """A single telemetry span representing one step in the decision pipeline."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    kind: SpanKind
    name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds; 0 if not ended."""
        if not self.ended_at:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds() * 1000.0

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        event = {"name": name, "timestamp": datetime.now(timezone.utc).isoformat()}
        if attributes:
            event["attributes"] = attributes
        self.events.append(event)


@dataclass
class TelemetryTrace:
    """A full trace with all spans collected across the pipeline."""
    trace_id: str
    portfolio_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    spans: List[TelemetrySpan] = field(default_factory=list)
    total_decisions: int = 0
    total_intents: int = 0
    status: SpanStatus = SpanStatus.OK
    error: Optional[str] = None

    @property
    def total_duration_ms(self) -> float:
        if not self.ended_at:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds() * 1000.0

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def error_spans(self) -> List[TelemetrySpan]:
        return [s for s in self.spans if s.status == SpanStatus.ERROR]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "portfolio_id": self.portfolio_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "total_decisions": self.total_decisions,
            "total_intents": self.total_intents,
            "status": self.status.value,
            "error": self.error,
            "span_count": self.span_count,
            "error_spans": len(self.error_spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "kind": s.kind.value,
                    "name": s.name,
                    "status": s.status.value,
                    "duration_ms": round(s.duration_ms, 3),
                    "attributes": s.attributes,
                    "events": s.events,
                    "error_message": s.error_message,
                }
                for s in self.spans
            ],
        }


# ---------------------------------------------------------------------------
# Portfolio Decision Telemetry
# ---------------------------------------------------------------------------

class PortfolioDecisionTelemetry:
    """Distributed telemetry for the portfolio decision pipeline.

    Traces every step: Sizing → Allocation → Exposure → Conflict → Netting → Intent.
    Each trace produces correlatable spans for end-to-end observability and audit.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        # Active traces keyed by trace_id
        self._traces: Dict[str, TelemetryTrace] = {}
        # Completed traces (circular buffer)
        self._completed: List[TelemetryTrace] = []
        self._max_completed = 100

        logger.info("PortfolioDecisionTelemetry initialized (enabled=%s)", enabled)

    # ------------------------------------------------------------------
    # Trace Lifecycle
    # ------------------------------------------------------------------

    def start_trace(self, portfolio_id: str) -> TelemetryTrace:
        """Start a new trace for a portfolio decision cycle."""
        trace = TelemetryTrace(
            trace_id=f"trace_{uuid4().hex[:12]}",
            portfolio_id=portfolio_id,
            started_at=datetime.now(timezone.utc),
        )
        self._traces[trace.trace_id] = trace
        logger.debug("Trace started: %s (portfolio=%s)", trace.trace_id, portfolio_id)
        return trace

    def end_trace(self, trace_id: str, status: SpanStatus = SpanStatus.OK,
                  error: Optional[str] = None) -> Optional[TelemetryTrace]:
        """End an active trace."""
        trace = self._traces.pop(trace_id, None)
        if not trace:
            logger.warning("Attempted to end unknown trace: %s", trace_id)
            return None

        trace.ended_at = datetime.now(timezone.utc)
        trace.status = status
        trace.error = error

        self._completed.append(trace)
        if len(self._completed) > self._max_completed:
            self._completed = self._completed[-self._max_completed:]

        logger.info("Trace ended: %s (duration=%s ms, spans=%d, intents=%d, status=%s)",
                     trace_id, round(trace.total_duration_ms, 2),
                     trace.span_count, trace.total_intents, status.value)
        return trace

    # ------------------------------------------------------------------
    # Span Creation
    # ------------------------------------------------------------------

    def start_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Start a new span within an existing trace."""
        span = TelemetrySpan(
            span_id=f"span_{uuid4().hex[:8]}",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name,
            started_at=datetime.now(timezone.utc),
            attributes=attributes or {},
        )

        trace = self._traces.get(trace_id)
        if trace:
            trace.spans.append(span)
        else:
            logger.warning("Span %s created for unknown trace %s", span.span_id, trace_id)

        logger.debug("Span started: %s [%s] -> trace=%s", name, kind.value, trace_id)
        return span

    def end_span(self, span: TelemetrySpan, status: SpanStatus = SpanStatus.OK,
                 error_message: Optional[str] = None,
                 attributes: Optional[Dict[str, Any]] = None) -> None:
        """End a span."""
        span.ended_at = datetime.now(timezone.utc)
        span.status = status
        span.error_message = error_message
        if attributes:
            span.attributes.update(attributes)

        logger.debug("Span ended: %s [%s] -> %s (%s ms)",
                     span.name, span.kind.value, status.value, round(span.duration_ms, 2))

    # ------------------------------------------------------------------
    # Pipeline-specific Convenience Methods
    # ------------------------------------------------------------------

    def trace_sizing(
        self, trace_id: str, parent_span_id: str,
        instrument: str, signal_strength: float, model: str,
    ) -> TelemetrySpan:
        """Create a trace span for the position sizing step."""
        return self.start_span(
            trace_id=trace_id,
            kind=SpanKind.SIZING,
            name=f"sizing:{instrument}",
            parent_span_id=parent_span_id,
            attributes={
                "instrument": instrument,
                "signal_strength": signal_strength,
                "sizing_model": model,
            },
        )

    def trace_allocation(
        self, trace_id: str, parent_span_id: str,
        strategy_id: str, requested_amount: float,
    ) -> TelemetrySpan:
        """Create a trace span for the capital allocation step."""
        return self.start_span(
            trace_id=trace_id,
            kind=SpanKind.ALLOCATION,
            name=f"allocation:{strategy_id}",
            parent_span_id=parent_span_id,
            attributes={
                "strategy_id": strategy_id,
                "requested_amount": requested_amount,
            },
        )

    def trace_decision(
        self, trace_id: str, parent_span_id: str,
        portfolio_id: str, signal_count: int,
    ) -> TelemetrySpan:
        """Create a trace span for the portfolio decision step."""
        return self.start_span(
            trace_id=trace_id,
            kind=SpanKind.DECISION,
            name=f"decision:{portfolio_id}",
            parent_span_id=parent_span_id,
            attributes={
                "portfolio_id": portfolio_id,
                "signal_count": signal_count,
            },
        )

    def trace_conflict(
        self, trace_id: str, parent_span_id: str,
        instrument: str, strategy_ids: List[str],
    ) -> TelemetrySpan:
        """Create a trace span for strategy conflict resolution."""
        return self.start_span(
            trace_id=trace_id,
            kind=SpanKind.CONFLICT,
            name=f"conflict:{instrument}",
            parent_span_id=parent_span_id,
            attributes={
                "instrument": instrument,
                "conflicting_strategies": strategy_ids,
                "conflict_count": len(strategy_ids),
            },
        )

    def trace_netting(
        self, trace_id: str, parent_span_id: str,
        instrument: str, original_count: int, netted_count: int,
    ) -> TelemetrySpan:
        """Create a trace span for order netting."""
        return self.start_span(
            trace_id=trace_id,
            kind=SpanKind.NETTING,
            name=f"netting:{instrument}",
            parent_span_id=parent_span_id,
            attributes={
                "instrument": instrument,
                "original_order_count": original_count,
                "netted_order_count": netted_count,
                "reduction": original_count - netted_count,
            },
        )

    def trace_intent(
        self, trace_id: str, parent_span_id: str,
        intent_id: str, instrument: str, direction: str, quantity: float,
    ) -> TelemetrySpan:
        """Create a trace span for an order intent."""
        span = self.start_span(
            trace_id=trace_id,
            kind=SpanKind.ORDER_INTENT,
            name=f"intent:{intent_id}",
            parent_span_id=parent_span_id,
            attributes={
                "intent_id": intent_id,
                "instrument": instrument,
                "direction": direction,
                "quantity": quantity,
            },
        )
        # Update trace intent counter
        trace = self._traces.get(trace_id)
        if trace:
            trace.total_intents += 1
        return span

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Optional[TelemetryTrace]:
        """Get an active or completed trace by ID."""
        active = self._traces.get(trace_id)
        if active:
            return active
        for t in reversed(self._completed):
            if t.trace_id == trace_id:
                return t
        return None

    def recent_traces(self, limit: int = 20) -> List[TelemetryTrace]:
        """Return the most recent completed traces."""
        return self._completed[-limit:]

    def active_trace_ids(self) -> List[str]:
        return list(self._traces.keys())

    def trace_count(self) -> Dict[str, int]:
        return {
            "active": len(self._traces),
            "completed": len(self._completed),
        }

    def latency_breakdown(self, trace_id: str) -> Optional[Dict[str, float]]:
        """Break down latency by span kind for a completed trace."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None

        breakdown: Dict[str, float] = {}
        for span in trace.spans:
            key = span.kind.value
            breakdown[key] = breakdown.get(key, 0.0) + span.duration_ms

        return breakdown

    def reset(self) -> None:
        """Clear all telemetry data."""
        self._traces.clear()
        self._completed.clear()
        logger.info("PortfolioDecisionTelemetry reset")

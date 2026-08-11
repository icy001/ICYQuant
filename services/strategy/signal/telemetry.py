"""
Alpha & Signal Telemetry — Distributed tracing and audit for signal/alpha pipelines.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Traces:
    - Alpha Timeline (generation → evaluation → decay)
    - Signal Timeline (generation → validation → publishing)
    - Validation Timeline (stage-by-stage)
    - Ranking Timeline
    - Full audit trail
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SpanKind(str, Enum):
    """Types of telemetry spans."""
    # Alpha lifecycle
    ALPHA_GENERATE = "alpha.generate"
    ALPHA_PIPELINE = "alpha.pipeline"
    ALPHA_COMBINE = "alpha.combine"
    ALPHA_QUALITY = "alpha.quality"
    ALPHA_DECAY = "alpha.decay"
    ALPHA_WEIGHT = "alpha.weight"

    # Signal lifecycle
    SIGNAL_GENERATE = "signal.generate"
    SIGNAL_VALIDATE = "signal.validate"
    SIGNAL_NORMALIZE = "signal.normalize"
    SIGNAL_RANK = "signal.rank"
    SIGNAL_CONFIDENCE = "signal.confidence"
    SIGNAL_EXPLAIN = "signal.explain"
    SIGNAL_PUBLISH = "signal.publish"
    SIGNAL_DISPATCH = "signal.dispatch"

    # System
    ENGINE_INIT = "engine.init"
    ENGINE_SHUTDOWN = "engine.shutdown"
    AUDIT = "audit"


@dataclass
class Span:
    """A single telemetry span."""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    kind: SpanKind = SpanKind.AUDIT
    name: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "ok"  # "ok", "error", "cancelled"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def finish(self, status: str = "ok", error: Optional[str] = None) -> None:
        self.finished_at = datetime.now(timezone.utc)
        self.duration_ms = (self.finished_at - self.started_at).total_seconds() * 1000
        self.status = status
        self.error_message = error

    def add_event(self, name: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "events": self.events,
        }


@dataclass
class Trace:
    """A complete trace composed of multiple spans."""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    root_span: Optional[Span] = None
    spans: List[Span] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }


# ---------------------------------------------------------------------------
# Alpha Signal Telemetry
# ---------------------------------------------------------------------------

class AlphaSignalTelemetry:
    """Distributed tracing for alpha and signal pipelines.

    Provides end-to-end visibility into:
        - Alpha generation pipeline latency
        - Signal validation stage timing
        - Dispatch delivery tracking
        - Audit trail for regulatory compliance
    """

    MAX_TRACES = 10_000

    def __init__(self):
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}

    # ------------------------------------------------------------------
    # Trace Management
    # ------------------------------------------------------------------

    def start_trace(self, name: str = "", metadata: Optional[Dict[str, Any]] = None) -> Trace:
        """Start a new trace."""
        trace = Trace(metadata=metadata or {})
        span = self.start_span(
            trace_id=trace.trace_id,
            kind=SpanKind.AUDIT,
            name=name or f"trace_{trace.trace_id[:8]}",
            metadata=metadata,
        )
        trace.root_span = span
        self._traces[trace.trace_id] = trace
        self._enforce_max_traces()
        return trace

    def finish_trace(self, trace_id: str, status: str = "ok") -> Optional[Trace]:
        """Finish a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.finished_at = datetime.now(timezone.utc)
        return trace

    # ------------------------------------------------------------------
    # Span Management
    # ------------------------------------------------------------------

    def start_span(self, trace_id: str, kind: SpanKind, name: str = "",
                   parent_span_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Span:
        """Start a new span within a trace."""
        span = Span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name or kind.value,
            metadata=metadata or {},
        )
        self._active_spans[span.span_id] = span

        # Attach to trace
        trace = self._traces.get(trace_id)
        if trace:
            trace.spans.append(span)

        return span

    def finish_span(self, span_id: str, status: str = "ok",
                    error: Optional[str] = None) -> Optional[Span]:
        """Finish a span."""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.finish(status=status, error=error)
        return span

    def add_span_event(self, span_id: str, name: str,
                       data: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to a span."""
        span = self._active_spans.get(span_id)
        if span:
            span.add_event(name, data)

    # ------------------------------------------------------------------
    # Convenience Methods for Alpha Pipeline
    # ------------------------------------------------------------------

    def trace_alpha_generation(self, alpha_id: str, instrument: str) -> Span:
        trace = self.start_trace(name=f"alpha:{alpha_id}:{instrument}")
        return self.start_span(
            trace_id=trace.trace_id,
            kind=SpanKind.ALPHA_GENERATE,
            name=f"Alpha {alpha_id} → {instrument}",
            parent_span_id=trace.root_span.span_id if trace.root_span else None,
            metadata={"alpha_id": alpha_id, "instrument": instrument},
        )

    def trace_signal_generation(self, strategy_id: str, count: int) -> Span:
        trace = self.start_trace(name=f"signal:{strategy_id}")
        return self.start_span(
            trace_id=trace.trace_id,
            kind=SpanKind.SIGNAL_GENERATE,
            name=f"Signal gen for {strategy_id}",
            parent_span_id=trace.root_span.span_id if trace.root_span else None,
            metadata={"strategy_id": strategy_id, "target_count": count},
        )

    def trace_signal_validation(self, signal_id: str) -> Span:
        return self.start_span(
            trace_id="",
            kind=SpanKind.SIGNAL_VALIDATE,
            name=f"Validate {signal_id}",
            metadata={"signal_id": signal_id},
        )

    def trace_signal_publish(self, count: int) -> Span:
        trace = self.start_trace(name="signal_publish")
        return self.start_span(
            trace_id=trace.trace_id,
            kind=SpanKind.SIGNAL_PUBLISH,
            name=f"Publish {count} signals",
            parent_span_id=trace.root_span.span_id if trace.root_span else None,
            metadata={"count": count},
        )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit(self, action: str, details: Dict[str, Any]) -> None:
        """Record an audit event."""
        trace = self.start_trace(name=f"audit:{action}")
        span = self.start_span(
            trace_id=trace.trace_id,
            kind=SpanKind.AUDIT,
            name=action,
            parent_span_id=trace.root_span.span_id if trace.root_span else None,
            metadata=details,
        )
        span.finish(status="ok")
        self.finish_trace(trace.trace_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._traces.get(trace_id)

    def list_recent_traces(self, limit: int = 50) -> List[Trace]:
        traces = list(self._traces.values())
        traces.sort(key=lambda t: t.started_at, reverse=True)
        return traces[:limit]

    def active_span_count(self) -> int:
        return len(self._active_spans)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enforce_max_traces(self) -> None:
        while len(self._traces) > self.MAX_TRACES:
            oldest_key = min(self._traces.keys(),
                             key=lambda k: self._traces[k].started_at)
            del self._traces[oldest_key]

    def clear(self) -> None:
        self._traces.clear()
        self._active_spans.clear()

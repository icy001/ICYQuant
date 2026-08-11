"""
Pre-Trade Telemetry — Distributed tracing for the pre-trade risk pipeline.

Provides structured telemetry traces covering the full evaluation
lifecycle: request intake, rule chain execution, approval routing,
and decision delivery.

Timeline::

    Request Timeline → Rule Timeline → Approval Timeline → Decision Timeline → Audit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TelemetryPhase(str, Enum):
    """Phases of the pre-trade evaluation pipeline."""
    REQUEST_RECEIVED = "request_received"
    CONTEXT_CREATED = "context_created"
    RULE_CHAIN_STARTED = "rule_chain_started"
    RULE_CHAIN_COMPLETED = "rule_chain_completed"
    CHECKER_STARTED = "checker_started"
    CHECKER_COMPLETED = "checker_completed"
    DECISION_BUILT = "decision_built"
    APPROVAL_ROUTED = "approval_routed"
    APPROVAL_RESOLVED = "approval_resolved"
    RESPONSE_SENT = "response_sent"


@dataclass
class TelemetrySpan:
    """A single span in a telemetry trace."""
    span_id: str = field(default_factory=lambda: uuid4().hex[:12])
    phase: TelemetryPhase = TelemetryPhase.REQUEST_RECEIVED
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_span_id: Optional[str] = None
    status: str = "ok"

    def complete(self, status: str = "ok") -> None:
        """Mark the span as complete."""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = (
            (self.completed_at - self.started_at).total_seconds() * 1000
        )
        self.status = status


@dataclass
class TelemetryTrace:
    """A full telemetry trace for a single pre-trade evaluation."""
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    request_id: str = ""
    spans: list[TelemetrySpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0

    def add_span(
        self,
        phase: TelemetryPhase,
        parent_span_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        span = TelemetrySpan(
            phase=phase,
            parent_span_id=parent_span_id,
            metadata=metadata or {},
        )
        self.spans.append(span)
        return span

    def complete(self) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.total_duration_ms = (
            (self.completed_at - self.started_at).total_seconds() * 1000
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "total_duration_ms": self.total_duration_ms,
            "span_count": len(self.spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "phase": s.phase.value,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "parent_span_id": s.parent_span_id,
                }
                for s in self.spans
            ],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PreTradeTelemetry:
    """
    Telemetry collector for the Pre-Trade Risk Platform.

    Creates and manages distributed traces for each evaluation,
    providing visibility into the full pipeline lifecycle.

    Usage::

        telemetry = PreTradeTelemetry()
        trace = telemetry.start_trace("REQ-001")
        span = trace.add_span(TelemetryPhase.CHECKER_STARTED)
        # ... do work ...
        span.complete()
        trace.complete()
        traces = telemetry.get_recent_traces()
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._max_traces = max_traces
        self._trace_count: int = 0
        self._span_count: int = 0

    def start_trace(self, request_id: str) -> TelemetryTrace:
        """Start a new telemetry trace for an evaluation."""
        trace = TelemetryTrace(request_id=request_id)
        trace.add_span(
            TelemetryPhase.REQUEST_RECEIVED,
            metadata={"request_id": request_id},
        )
        self._traces[trace.trace_id] = trace
        self._trace_count += 1

        # Evict old traces
        if len(self._traces) > self._max_traces:
            oldest = sorted(
                self._traces.keys(),
                key=lambda tid: self._traces[tid].started_at,
            )[:len(self._traces) - self._max_traces]
            for tid in oldest:
                del self._traces[tid]

        return trace

    def get_trace(self, trace_id: str) -> Optional[TelemetryTrace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 50) -> list[TelemetryTrace]:
        """Get most recent traces."""
        return sorted(
            self._traces.values(),
            key=lambda t: t.started_at,
            reverse=True,
        )[:limit]

    def record_span(self, span: TelemetrySpan) -> None:
        """Record a standalone span count."""
        self._span_count += 1

    def stats(self) -> dict[str, Any]:
        """Get telemetry statistics."""
        traces = list(self._traces.values())
        completed = [t for t in traces if t.completed_at is not None]
        avg_duration = (
            sum(t.total_duration_ms for t in completed) / len(completed)
            if completed
            else 0.0
        )
        return {
            "total_traces": self._trace_count,
            "active_traces": len(traces) - len(completed),
            "completed_traces": len(completed),
            "avg_duration_ms": avg_duration,
            "max_stored_traces": self._max_traces,
        }

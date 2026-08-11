"""
Distributed tracing and telemetry for AI Agent operations.

Traces the complete agent execution pipeline:
    AI Agent → Tracing → Planning Timeline → Execution Timeline
    → Memory Timeline → Audit

Provides observability into agent decision-making and execution flow.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Telemetry Types ──


class SpanKind(str, Enum):
    """Span operation types."""

    AGENT = "agent"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTION = "execution"
    MEMORY = "memory"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"


class SpanStatus(str, Enum):
    """Span completion status."""

    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """A single span in a trace."""

    span_id: str = field(default_factory=lambda: uuid4().hex)
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    name: str = ""
    kind: SpanKind = SpanKind.AGENT
    status: SpanStatus = SpanStatus.OK
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Span duration in seconds."""
        end = self.end_time or time.monotonic()
        return end - self.start_time


@dataclass
class Trace:
    """A complete trace containing multiple spans."""

    trace_id: str = field(default_factory=lambda: uuid4().hex)
    root_span_id: str = ""
    spans: List[Span] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_span(self, span: Span) -> None:
        """Add a span to the trace."""
        self.spans.append(span)

    def get_total_duration(self) -> float:
        """Total trace duration."""
        return sum(s.duration_seconds for s in self.spans)

    def to_summary(self) -> Dict[str, Any]:
        """Get trace summary."""
        return {
            "trace_id": self.trace_id,
            "span_count": len(self.spans),
            "total_duration_seconds": self.get_total_duration(),
            "spans": [
                {
                    "name": s.name,
                    "kind": s.kind.value,
                    "duration": s.duration_seconds,
                    "status": s.status.value,
                }
                for s in self.spans
            ],
        }


# ── Agent Telemetry ──


class AgentTelemetry:
    """Tracing and telemetry system for agent operations.

    Captures execution traces with planning, reasoning, and
    memory timelines for debugging and audit purposes.

    Usage:
        telemetry = AgentTelemetry()
        trace = telemetry.start_trace("analyze_market")
        span = telemetry.start_span(trace.trace_id, "planning", SpanKind.PLANNING)
        # ... do work ...
        telemetry.end_span(span.span_id)
        summary = telemetry.get_trace(trace.trace_id)
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self.max_traces = max_traces
        self._traces: Dict[str, Trace] = {}
        self._spans: Dict[str, Span] = {}
        self._active_traces: List[str] = []
        self._trace_count: int = 0
        logger.info("AgentTelemetry initialized")

    # ── Trace Management ──

    def start_trace(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Trace:
        """Start a new trace.

        Args:
            name: Trace name (e.g., operation name).
            metadata: Additional trace metadata.

        Returns:
            New Trace object.
        """
        self._trace_count += 1
        trace = Trace(
            metadata=metadata or {},
        )

        # Create root span
        root_span = Span(
            trace_id=trace.trace_id,
            name=name,
            kind=SpanKind.AGENT,
        )
        trace.root_span_id = root_span.span_id
        trace.add_span(root_span)
        self._spans[root_span.span_id] = root_span

        self._traces[trace.trace_id] = trace
        self._active_traces.append(trace.trace_id)

        # Enforce capacity
        if len(self._traces) > self.max_traces:
            oldest_id = min(
                self._traces.keys(),
                key=lambda tid: self._traces[tid].created_at,
            )
            del self._traces[oldest_id]

        logger.debug(f"Trace started: {trace.trace_id} [{name}]")
        return trace

    # ── Span Management ──

    def start_span(
        self,
        trace_id: str,
        name: str,
        kind: SpanKind,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span within a trace.

        Args:
            trace_id: Parent trace ID.
            name: Span name.
            kind: Span kind.
            parent_span_id: Optional parent span.
            attributes: Span attributes.

        Returns:
            New Span object.
        """
        span = Span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )
        self._spans[span.span_id] = span

        trace = self._traces.get(trace_id)
        if trace:
            trace.add_span(span)

        logger.debug(f"Span started: {span.span_id} [{name}]")
        return span

    def end_span(
        self,
        span_id: str,
        status: SpanStatus = SpanStatus.OK,
        error: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """End a span.

        Args:
            span_id: Span identifier.
            status: Completion status.
            error: Error message if failed.
            attributes: Additional attributes.

        Returns:
            True if span was ended.
        """
        span = self._spans.get(span_id)
        if not span:
            return False

        span.end_time = time.monotonic()
        span.status = status
        if error:
            span.error = error
        if attributes:
            span.attributes.update(attributes)

        logger.debug(
            f"Span ended: {span_id} [{span.status.value}] {span.duration_seconds:.3f}s",
        )
        return True

    def add_event(
        self,
        span_id: str,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a timestamped event to a span.

        Args:
            span_id: Span identifier.
            name: Event name.
            attributes: Event attributes.

        Returns:
            True if event was added.
        """
        span = self._spans.get(span_id)
        if not span:
            return False

        span.events.append({
            "name": name,
            "timestamp": time.monotonic(),
            "attributes": attributes or {},
        })
        return True

    # ── Query ──

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a complete trace by ID."""
        return self._traces.get(trace_id)

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    def get_active_traces(self) -> List[Trace]:
        """Get all currently active traces."""
        return [self._traces[tid] for tid in self._active_traces if tid in self._traces]

    def list_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List most recent traces."""
        sorted_traces = sorted(
            self._traces.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )
        return [t.to_summary() for t in sorted_traces[:limit]]

    # ── Cleanup ──

    def cleanup_old_traces(self, max_age_seconds: float = 3600.0) -> int:
        """Remove traces older than max_age_seconds.

        Returns:
            Number of traces removed.
        """
        now = time.monotonic()
        to_remove = []
        for tid, trace in self._traces.items():
            trace_age = now - trace.created_at.timestamp()
            if trace_age > max_age_seconds:
                to_remove.append(tid)

        for tid in to_remove:
            del self._traces[tid]

        return len(to_remove)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get telemetry summary."""
        return {
            "total_traces": self._trace_count,
            "stored_traces": len(self._traces),
            "active_traces": len(self._active_traces),
            "total_spans": len(self._spans),
        }

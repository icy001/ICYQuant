"""Tool Telemetry — distributed tracing for tool calling lifecycle.

Pipeline:
    Tool Calling
        -> Tracing (span creation, context propagation)
        -> Execution Timeline
        -> Observation Timeline
        -> Audit
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Enums ──

class SpanKind(str, Enum):
    """Type of telemetry span."""

    TOOL_CALL = "tool_call"
    VALIDATION = "validation"
    PERMISSION_CHECK = "permission_check"
    POLICY_CHECK = "policy_check"
    SANDBOX_CHECK = "sandbox_check"
    CACHE_LOOKUP = "cache_lookup"
    RETRY = "retry"
    RECOVERY = "recovery"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class SpanStatus(str, Enum):
    """Status of a span."""

    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


# ── Span ──

@dataclass
class Span:
    """A single telemetry span within a trace."""

    span_id: str = field(default_factory=lambda: uuid4().hex)
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    name: str = ""
    kind: SpanKind = SpanKind.TOOL_CALL
    status: SpanStatus = SpanStatus.OK

    # ── Timing ──
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0

    # ── Attributes ──
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    def start(self) -> None:
        """Start the span."""
        self.start_time = datetime.now(timezone.utc)

    def end(self, status: SpanStatus = SpanStatus.OK) -> None:
        """End the span."""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name.
            attributes: Optional event attributes.
        """
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_error(self, message: str) -> None:
        """Mark the span as error.

        Args:
            message: Error description.
        """
        self.status = SpanStatus.ERROR
        self.error_message = message

    def to_dict(self) -> Dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
            "events": self.events,
            "error_message": self.error_message,
        }


# ── Trace ──

@dataclass
class Trace:
    """A complete telemetry trace for a tool execution."""

    trace_id: str = field(default_factory=lambda: uuid4().hex)
    tool_name: str = ""
    session_id: str = ""
    agent_id: str = ""
    spans: List[Span] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def has_errors(self) -> bool:
        return any(s.status == SpanStatus.ERROR for s in self.spans)

    def add_span(self, span: Span) -> Span:
        """Add a span to the trace.

        Args:
            span: The span to add.

        Returns:
            The added span.
        """
        span.trace_id = self.trace_id
        self.spans.append(span)
        return span

    def finalize(self) -> None:
        """Finalize the trace."""
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace to dictionary."""
        return {
            "trace_id": self.trace_id,
            "tool_name": self.tool_name,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "duration_ms": round(self.duration_ms, 2),
            "span_count": self.span_count,
            "has_errors": self.has_errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "spans": [s.to_dict() for s in self.spans],
        }


# ── ToolTelemetry ──

class ToolTelemetry:
    """Distributed tracing for the tool calling subsystem.

    Creates and manages traces and spans for each tool execution,
    providing full visibility into the execution timeline including
    validation, permission checks, cache lookups, and more.

    Supports:
        - Trace and span lifecycle management
        - Parent-child span relationships
        - Event recording within spans
        - Error annotation
        - Timeline visualization data
        - Capacity control with max_traces

    Usage:
        telemetry = ToolTelemetry(max_traces=1000)
        trace = telemetry.start_trace("backtest.run")
        span = telemetry.start_span(trace, "validation", SpanKind.VALIDATION)
        span.add_event("schema_check_passed")
        telemetry.end_span(span)
        telemetry.end_trace(trace)
    """

    def __init__(self, max_traces: int = 1000) -> None:
        """Initialize telemetry.

        Args:
            max_traces: Maximum number of completed traces to retain.
        """
        self._max_traces = max_traces
        self._active_traces: Dict[str, Trace] = {}
        self._completed_traces: List[Trace] = []

        self._initialized: bool = False
        logger.info(f"ToolTelemetry created (max_traces={max_traces})")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize telemetry."""
        self._initialized = True
        logger.info("ToolTelemetry initialized")

    async def shutdown(self) -> None:
        """Shutdown telemetry."""
        self._active_traces.clear()
        self._completed_traces.clear()
        self._initialized = False
        logger.info("ToolTelemetry shutdown complete")

    # ── Trace Management ──

    def start_trace(
        self,
        tool_name: str,
        session_id: str = "",
        agent_id: str = "",
    ) -> Trace:
        """Start a new execution trace.

        Args:
            tool_name: The tool being executed.
            session_id: The session identifier.
            agent_id: The agent identifier.

        Returns:
            A new Trace instance.
        """
        trace = Trace(
            tool_name=tool_name,
            session_id=session_id,
            agent_id=agent_id,
        )
        self._active_traces[trace.trace_id] = trace
        logger.debug(f"Trace started: {trace.trace_id} for {tool_name}")
        return trace

    def end_trace(self, trace: Trace) -> None:
        """End an execution trace.

        Args:
            trace: The trace to end.
        """
        trace.finalize()
        self._active_traces.pop(trace.trace_id, None)
        self._completed_traces.append(trace)

        # Enforce max capacity
        if len(self._completed_traces) > self._max_traces:
            self._completed_traces = self._completed_traces[-self._max_traces:]

        logger.debug(
            f"Trace ended: {trace.trace_id} ({trace.duration_ms:.1f}ms, "
            f"{trace.span_count} spans)"
        )

    # ── Span Management ──

    def start_span(
        self,
        trace: Trace,
        name: str,
        kind: SpanKind,
        parent_span: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span within a trace.

        Args:
            trace: The parent trace.
            name: Span name.
            kind: Span kind.
            parent_span: Optional parent span.
            attributes: Optional span attributes.

        Returns:
            A new Span instance.
        """
        span = Span(
            name=name,
            kind=kind,
            parent_span_id=parent_span.span_id if parent_span else None,
            attributes=attributes or {},
        )
        span.start()
        trace.add_span(span)
        logger.debug(f"Span started: {span.span_id} ({name}, kind={kind.value})")
        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span.

        Args:
            span: The span to end.
            status: Final status.
        """
        span.end(status)
        logger.debug(
            f"Span ended: {span.span_id} status={status.value} ({span.duration_ms:.1f}ms)"
        )

    def span_error(self, span: Span, error_message: str) -> None:
        """Mark a span as errored.

        Args:
            span: The span to mark.
            error_message: Error description.
        """
        span.set_error(error_message)
        span.add_event("error", {"message": error_message})

    # ── Queries ──

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID.

        Args:
            trace_id: The trace identifier.

        Returns:
            The Trace, or None if not found.
        """
        # Check active traces first
        if trace_id in self._active_traces:
            return self._active_traces[trace_id]
        # Then completed traces
        for trace in self._completed_traces:
            if trace.trace_id == trace_id:
                return trace
        return None

    def get_recent_traces(self, limit: int = 20) -> List[Trace]:
        """Get the most recent completed traces.

        Args:
            limit: Maximum number of traces.

        Returns:
            List of recent traces.
        """
        return self._completed_traces[-limit:]

    def get_traces_by_tool(self, tool_name: str, limit: int = 20) -> List[Trace]:
        """Get traces for a specific tool.

        Args:
            tool_name: The tool name.
            limit: Maximum results.

        Returns:
            List of matching traces.
        """
        matching = [t for t in self._completed_traces if t.tool_name == tool_name]
        return matching[-limit:]

    # ── Timeline Data ──

    def get_execution_timeline(self, trace_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get a time-ordered timeline of spans for visualization.

        Args:
            trace_id: The trace identifier.

        Returns:
            List of timeline entries, or None.
        """
        trace = self.get_trace(trace_id)
        if trace is None:
            return None

        timeline = []
        for span in trace.spans:
            timeline.append({
                "span_id": span.span_id,
                "name": span.name,
                "kind": span.kind.value,
                "status": span.status.value,
                "start_offset_ms": (
                    (span.start_time - trace.started_at).total_seconds() * 1000
                    if span.start_time
                    else 0
                ),
                "duration_ms": round(span.duration_ms, 2),
                "parent_span_id": span.parent_span_id,
            })

        timeline.sort(key=lambda e: e["start_offset_ms"])
        return timeline

    # ── Cleanup ──

    def cleanup_old_traces(self, max_age_seconds: float = 3600.0) -> int:
        """Remove traces older than a threshold.

        Args:
            max_age_seconds: Maximum age in seconds.

        Returns:
            Number of traces removed.
        """
        cutoff = datetime.now(timezone.utc)
        count = 0
        kept = []
        for trace in self._completed_traces:
            if trace.started_at and (cutoff - trace.started_at).total_seconds() < max_age_seconds:
                kept.append(trace)
            else:
                count += 1
        self._completed_traces = kept
        if count:
            logger.info(f"Cleaned up {count} old traces")
        return count

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get telemetry status."""
        return {
            "active_traces": len(self._active_traces),
            "completed_traces": len(self._completed_traces),
            "max_traces": self._max_traces,
            "initialized": self._initialized,
        }

"""Collaboration Telemetry — distributed tracing for multi-agent coordination workflows.

Tracks the full lifecycle of agent collaboration with spans for:
    - coordinator_timeline    — coordinator planning & assignment
    - agent_timeline           — per-agent task execution
    - message_timeline         — message routing & delivery
    - consensus_timeline       — voting & consensus decisions
    - audit                    — end-to-end decision audit trail

All spans are collected into Traces which can be exported to
OpenTelemetry, Jaeger, or the ICYQuant monitoring dashboard.

Span Types:
    COORDINATOR_DECIDE    — coordinator making assignment decisions
    COORDINATOR_DISPATCH  — coordinator dispatching tasks
    AGENT_RECEIVE         — agent receiving a task/message
    AGENT_PROCESS         — agent processing a task
    AGENT_RESPOND         — agent producing a result
    MESSAGE_SEND          — message sent over the bus
    MESSAGE_DELIVER       — message delivered to recipient
    CONSENSUS_COLLECT     — collecting votes from agents
    CONSENSUS_DECIDE      — final consensus decision
    AUDIT_DECISION        — audit log entry for a decision
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Span Types ──

class SpanType(str, Enum):
    """Types of telemetry spans in the collaboration pipeline."""

    COORDINATOR_DECIDE = "coordinator.decide"
    COORDINATOR_DISPATCH = "coordinator.dispatch"
    AGENT_RECEIVE = "agent.receive"
    AGENT_PROCESS = "agent.process"
    AGENT_RESPOND = "agent.respond"
    MESSAGE_SEND = "message.send"
    MESSAGE_DELIVER = "message.deliver"
    CONSENSUS_COLLECT = "consensus.collect"
    CONSENSUS_DECIDE = "consensus.decide"
    AUDIT_DECISION = "audit.decision"


# ── Span ──

@dataclass
class Span:
    """A single telemetry span within a collaboration trace.

    Attributes:
        span_id: Unique span identifier.
        trace_id: Parent trace identifier.
        parent_span_id: Optional parent span for nesting.
        span_type: The type of span.
        agent_id: Agent identifier if applicable.
        start_time: When the span started.
        end_time: When the span ended (None if still open).
        attributes: Key-value metadata.
        events: Timed events within this span.
        status: ok / error / unknown.
    """

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    span_type: SpanType = SpanType.AGENT_PROCESS
    agent_id: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"

    @property
    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds, or None if span is still open."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add a timed event to the span.

        Args:
            name: Event name.
            attributes: Optional event metadata.
        """
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "ok", attributes: Optional[Dict[str, Any]] = None) -> None:
        """Mark the span as finished.

        Args:
            status: "ok" or "error".
            attributes: Optional final attributes to merge.
        """
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        if attributes:
            self.attributes.update(attributes)

    def as_dict(self) -> Dict[str, Any]:
        """Serialize the span to a JSON-safe dict.

        Returns:
            Dict representation of the span.
        """
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "span_type": self.span_type.value,
            "agent_id": self.agent_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }


# ── Trace ──

@dataclass
class Trace:
    """A complete collaboration trace containing multiple spans.

    Attributes:
        trace_id: Unique trace identifier.
        goal: The original user goal that triggered this trace.
        start_time: When the trace started.
        end_time: When the trace ended (None if still active).
        spans: All spans in this trace.
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    goal: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    spans: List[Span] = field(default_factory=list)

    def create_span(
        self,
        span_type: SpanType,
        agent_id: str = "",
        parent_span_id: Optional[str] = None,
    ) -> Span:
        """Create a new child span in this trace.

        Args:
            span_type: Type of the span.
            agent_id: Agent identifier.
            parent_span_id: Optional parent span.

        Returns:
            The new Span.
        """
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            span_type=span_type,
            agent_id=agent_id,
        )
        self.spans.append(span)
        return span

    def finish(self) -> None:
        """Mark the entire trace as finished."""
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration_ms(self) -> Optional[float]:
        """Total trace duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def timeline(self) -> List[Dict[str, Any]]:
        """Return a time-sorted timeline of all spans.

        Returns:
            List of span dicts sorted by start_time.
        """
        return sorted(
            [s.as_dict() for s in self.spans],
            key=lambda s: s["start_time"],
        )

    def as_dict(self) -> Dict[str, Any]:
        """Serialize the trace to a JSON-safe dict.

        Returns:
            Dict representation of the trace.
        """
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "span_count": len(self.spans),
            "spans": self.timeline(),
        }


# ── Telemetry ──

class CollaborationTelemetry:
    """Central telemetry collector for multi-agent collaboration.

    Creates traces and spans that follow the full collaboration pipeline:
        Coordinator Timeline -> Agent Timeline -> Message Timeline ->
        Consensus Timeline -> Audit

    Usage:
        telemetry = CollaborationTelemetry()
        trace = telemetry.start_trace(goal="Analyze AAPL")
        span = trace.create_span(SpanType.AGENT_PROCESS, agent_id="market_agent")
        span.finish(status="ok")
        trace.finish()
    """

    def __init__(self, max_traces: int = 1000) -> None:
        """Initialize the telemetry collector.

        Args:
            max_traces: Maximum traces to retain in memory.
        """
        self._lock = threading.Lock()
        self._traces: Dict[str, Trace] = {}
        self._max_traces = max_traces
        self._active_traces: Dict[str, Trace] = {}
        logger.info("CollaborationTelemetry initialized (max_traces=%d)", max_traces)

    # ── Trace Management ──

    def start_trace(self, goal: str = "") -> Trace:
        """Start a new collaboration trace.

        Args:
            goal: The user goal that triggered this trace.

        Returns:
            The new Trace.
        """
        trace = Trace(goal=goal)
        with self._lock:
            self._active_traces[trace.trace_id] = trace
        logger.info("Trace started: id=%s goal=%s", trace.trace_id, goal)
        return trace

    def finish_trace(self, trace: Trace) -> None:
        """Finish a trace and archive it.

        Args:
            trace: The trace to finish.
        """
        trace.finish()
        with self._lock:
            self._active_traces.pop(trace.trace_id, None)
            self._traces[trace.trace_id] = trace

            # Evict oldest if over limit
            while len(self._traces) > self._max_traces:
                oldest = min(self._traces, key=lambda k: self._traces[k].start_time)
                del self._traces[oldest]

        logger.info(
            "Trace finished: id=%s duration=%.1fms spans=%d",
            trace.trace_id, trace.duration_ms, len(trace.spans),
        )

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID.

        Args:
            trace_id: The trace identifier.

        Returns:
            Trace or None.
        """
        with self._lock:
            return self._traces.get(trace_id) or self._active_traces.get(trace_id)

    # ── Coordinator Timeline ──

    def record_coordinator_decide(
        self,
        trace: Trace,
        agent_id: str,
        decision: Dict[str, Any],
    ) -> Span:
        """Record a coordinator decision span.

        Args:
            trace: The parent trace.
            agent_id: Coordinator agent ID.
            decision: The decision details.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.COORDINATOR_DECIDE, agent_id=agent_id)
        span.attributes["decision"] = decision
        span.status = "ok"
        span.finish()
        return span

    def record_coordinator_dispatch(
        self,
        trace: Trace,
        coordinator_id: str,
        target_agent: str,
        task: Dict[str, Any],
    ) -> Span:
        """Record a coordinator dispatch span.

        Args:
            trace: The parent trace.
            coordinator_id: Coordinator agent ID.
            target_agent: Destination agent.
            task: Task details.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.COORDINATOR_DISPATCH, agent_id=coordinator_id)
        span.attributes["target_agent"] = target_agent
        span.attributes["task"] = task
        span.status = "ok"
        span.finish()
        return span

    # ── Agent Timeline ──

    def record_agent_receive(
        self,
        trace: Trace,
        agent_id: str,
        message: Dict[str, Any],
    ) -> Span:
        """Record an agent receive span.

        Args:
            trace: The parent trace.
            agent_id: Receiving agent ID.
            message: Message details.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.AGENT_RECEIVE, agent_id=agent_id)
        span.attributes["message"] = message
        span.status = "ok"
        span.finish()
        return span

    def record_agent_process(
        self,
        trace: Trace,
        agent_id: str,
        task: Dict[str, Any],
    ) -> Span:
        """Record an agent processing span.

        Args:
            trace: The parent trace.
            agent_id: Processing agent ID.
            task: Task details.

        Returns:
            The created span (call finish() on it when processing completes).
        """
        span = trace.create_span(SpanType.AGENT_PROCESS, agent_id=agent_id)
        span.attributes["task"] = task
        return span

    def record_agent_respond(
        self,
        trace: Trace,
        agent_id: str,
        result: Any,
    ) -> Span:
        """Record an agent response span.

        Args:
            trace: The parent trace.
            agent_id: Responding agent ID.
            result: Result data.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.AGENT_RESPOND, agent_id=agent_id)
        span.attributes["result"] = result
        span.status = "ok"
        span.finish()
        return span

    # ── Message Timeline ──

    def record_message_send(
        self,
        trace: Trace,
        sender_id: str,
        recipient_id: str,
        message_type: str,
    ) -> Span:
        """Record a message send span.

        Args:
            trace: The parent trace.
            sender_id: Sending agent ID.
            recipient_id: Receiving agent ID.
            message_type: Type of message.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.MESSAGE_SEND, agent_id=sender_id)
        span.attributes["recipient"] = recipient_id
        span.attributes["message_type"] = message_type
        span.status = "ok"
        span.finish()
        return span

    def record_message_deliver(
        self,
        trace: Trace,
        recipient_id: str,
        message_type: str,
    ) -> Span:
        """Record a message delivery span.

        Args:
            trace: The parent trace.
            recipient_id: Receiving agent ID.
            message_type: Type of message.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.MESSAGE_DELIVER, agent_id=recipient_id)
        span.attributes["message_type"] = message_type
        span.status = "ok"
        span.finish()
        return span

    # ── Consensus Timeline ──

    def record_consensus_collect(
        self,
        trace: Trace,
        voter_count: int,
        topic: str,
    ) -> Span:
        """Record a consensus vote collection span.

        Args:
            trace: The parent trace.
            voter_count: Number of agents voting.
            topic: Decision topic.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.CONSENSUS_COLLECT)
        span.attributes["voter_count"] = voter_count
        span.attributes["topic"] = topic
        span.status = "ok"
        span.finish()
        return span

    def record_consensus_decide(
        self,
        trace: Trace,
        decision: str,
        confidence: float,
    ) -> Span:
        """Record a consensus decision span.

        Args:
            trace: The parent trace.
            decision: The final decision.
            confidence: Decision confidence score.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.CONSENSUS_DECIDE)
        span.attributes["decision"] = decision
        span.attributes["confidence"] = confidence
        span.status = "ok"
        span.finish()
        return span

    # ── Audit ──

    def record_audit_decision(
        self,
        trace: Trace,
        decision: str,
        reason: str,
    ) -> Span:
        """Record an audit decision span.

        Args:
            trace: The parent trace.
            decision: The decision made.
            reason: Rationale for the decision.

        Returns:
            The created span.
        """
        span = trace.create_span(SpanType.AUDIT_DECISION)
        span.attributes["decision"] = decision
        span.attributes["reason"] = reason
        span.status = "ok"
        span.finish()
        return span

    # ── Queries ──

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent completed traces.

        Args:
            limit: Maximum number of traces.

        Returns:
            List of trace summaries.
        """
        with self._lock:
            recent = sorted(
                self._traces.values(),
                key=lambda t: t.start_time,
                reverse=True,
            )[:limit]
        return [t.as_dict() for t in recent]

    def get_trace_count(self) -> Dict[str, int]:
        """Get counts of active and archived traces.

        Returns:
            Dict with active and archived counts.
        """
        with self._lock:
            return {
                "active": len(self._active_traces),
                "archived": len(self._traces),
            }

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the telemetry collector state.

        Returns:
            Dict with trace counts.
        """
        with self._lock:
            return {
                "active_traces": len(self._active_traces),
                "archived_traces": len(self._traces),
                "max_traces": self._max_traces,
            }

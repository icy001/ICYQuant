"""
ICYQuant Agent Telemetry — distributed tracing for multi-agent workflows.

Provides OpenTelemetry-compatible tracing with span creation, context
propagation, and event logging across agent interactions. Traces span
the full lifecycle of a multi-agent research workflow.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """OpenTelemetry span kinds."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatusCode(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """An event within a span."""
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A single trace span."""
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    trace_id: str = ""
    parent_span_id: str = ""
    name: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatusCode = SpanStatusCode.UNSET
    status_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@dataclass
class TraceContext:
    """Carrier for trace context across services."""
    trace_id: str = ""
    span_id: str = ""
    trace_flags: int = 0
    trace_state: str = ""
    baggage: dict[str, str] = field(default_factory=dict)


class AgentTelemetry:
    """Distributed tracing for multi-agent workflows.

    Trace kinds:
        1. orchestrator.execute — Full orchestration pipeline
        2. agent.task — Individual agent task execution
        3. agent.communicate — Inter-agent message exchange
        4. debate.session — Debate session lifecycle
        5. consensus.build — Consensus building process
        6. guardrail.evaluate — Guardrail evaluation
    """

    def __init__(self) -> None:
        self._spans: dict[str, Span] = {}
        self._active_traces: dict[str, list[str]] = {}  # trace_id → list of span_ids
        self._total_spans = 0

    # ── Span Management ──

    def start_span(self, name: str,
                   trace_id: Optional[str] = None,
                   parent_span_id: str = "",
                   kind: SpanKind = SpanKind.INTERNAL,
                   attributes: Optional[dict[str, Any]] = None) -> Span:
        """Start a new span. Creates a new trace if no trace_id provided."""
        self._total_spans += 1

        if trace_id is None:
            trace_id = str(uuid.uuid4())

        span = Span(
            span_id=str(uuid.uuid4())[:16],
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )
        self._spans[span.span_id] = span

        if trace_id not in self._active_traces:
            self._active_traces[trace_id] = []
        self._active_traces[trace_id].append(span.span_id)

        logger.debug("Span started: id=%s trace=%s name=%s",
                      span.span_id, trace_id, name)
        return span

    def end_span(self, span_id: str,
                 status: SpanStatusCode = SpanStatusCode.OK,
                 status_message: str = "") -> Optional[Span]:
        """End a span and record its status."""
        span = self._spans.get(span_id)
        if span is None:
            return None

        span.end_time = time.time()
        span.status = status
        span.status_message = status_message

        logger.debug("Span ended: id=%s name=%s duration=%.2fms status=%s",
                      span_id, span.name, span.duration_ms, status.value)
        return span

    def add_event(self, span_id: str, event_name: str,
                  attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to a span."""
        span = self._spans.get(span_id)
        if span is None:
            return

        event = SpanEvent(name=event_name, attributes=attributes or {})
        span.events.append(event)

    def set_attribute(self, span_id: str, key: str, value: Any) -> None:
        """Set an attribute on a span."""
        span = self._spans.get(span_id)
        if span is None:
            return
        span.attributes[key] = value

    # ── Trace Queries ──

    def get_trace(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace."""
        span_ids = self._active_traces.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def get_span(self, span_id: str) -> Optional[Span]:
        return self._spans.get(span_id)

    def trace_duration_ms(self, trace_id: str) -> float:
        """Get total trace duration."""
        spans = self.get_trace(trace_id)
        if not spans:
            return 0.0

        starts = [s.start_time for s in spans]
        ends = [s.end_time for s in spans if s.end_time]
        if not ends:
            return 0.0

        return (max(ends) - min(starts)) * 1000

    # ── Specialized trace helpers ──

    def trace_orchestration(self, request_id: str) -> tuple[str, str]:
        """Start an orchestration trace. Returns (trace_id, span_id)."""
        span = self.start_span(
            name="orchestrator.execute",
            kind=SpanKind.INTERNAL,
            attributes={"request_id": request_id},
        )
        return span.trace_id, span.span_id

    def trace_agent_task(self, trace_id: str, parent_span_id: str,
                         agent_id: str, task_id: str,
                         capability: str) -> str:
        """Start a trace for an agent task execution. Returns span_id."""
        span = self.start_span(
            name="agent.task",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.INTERNAL,
            attributes={
                "agent_id": agent_id,
                "task_id": task_id,
                "capability": capability,
            },
        )
        return span.span_id

    def trace_communication(self, trace_id: str, parent_span_id: str,
                            sender: str, recipient: str,
                            msg_type: str) -> str:
        """Trace an inter-agent communication. Returns span_id."""
        span = self.start_span(
            name="agent.communicate",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.PRODUCER,
            attributes={
                "sender_id": sender,
                "recipient_id": recipient,
                "message_type": msg_type,
            },
        )
        return span.span_id

    def trace_debate(self, trace_id: str, parent_span_id: str,
                     debate_id: str, topic: str) -> str:
        """Trace a debate session. Returns span_id."""
        span = self.start_span(
            name="debate.session",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.INTERNAL,
            attributes={"debate_id": debate_id, "topic": topic},
        )
        return span.span_id

    def trace_consensus(self, trace_id: str, parent_span_id: str) -> str:
        """Trace consensus building. Returns span_id."""
        span = self.start_span(
            name="consensus.build",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.INTERNAL,
        )
        return span.span_id

    def trace_guardrail(self, trace_id: str, parent_span_id: str,
                        request_id: str, action: str) -> str:
        """Trace guardrail evaluation. Returns span_id."""
        span = self.start_span(
            name="guardrail.evaluate",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.INTERNAL,
            attributes={"request_id": request_id, "action": action},
        )
        return span.span_id

    # ── Context Propagation ──

    def create_context(self, span: Span) -> TraceContext:
        """Create a trace context for propagation."""
        return TraceContext(
            trace_id=span.trace_id,
            span_id=span.span_id,
        )

    # ── Cleanup ──

    def cleanup_old_traces(self, max_age_seconds: int = 3600) -> int:
        """Clean up traces older than max_age_seconds."""
        now = time.time()
        removed = 0
        for trace_id in list(self._active_traces.keys()):
            spans = self.get_trace(trace_id)
            if spans and all(
                s.end_time and (now - s.end_time) > max_age_seconds
                for s in spans
            ):
                for s in spans:
                    self._spans.pop(s.span_id, None)
                self._active_traces.pop(trace_id, None)
                removed += 1
        return removed

    @property
    def total_spans(self) -> int:
        return self._total_spans

    @property
    def active_trace_count(self) -> int:
        return len(self._active_traces)

    @property
    def span_count(self) -> int:
        return len(self._spans)

"""Autonomy Telemetry — distributed tracing for autonomous research workflows.

Tracks the full autonomy pipeline with spans:
    - autonomy_timeline      — overall autonomous workflow
    - research_timeline       — research phase (signal, factor, hypothesis)
    - approval_timeline       — HITL approval phase
    - learning_timeline       — continuous learning phase
    - audit                   — full decision audit trail
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpanType(str, Enum):
    AUTONOMY_START = "autonomy.start"
    AUTONOMY_MONITOR = "autonomy.monitor"
    AUTONOMY_RESEARCH = "autonomy.research"
    AUTONOMY_BACKTEST = "autonomy.backtest"
    AUTONOMY_PORTFOLIO = "autonomy.portfolio"
    AUTONOMY_RISK = "autonomy.risk"
    AUTONOMY_COMPLIANCE = "autonomy.compliance"
    AUTONOMY_APPROVAL = "autonomy.approval"
    AUTONOMY_EXECUTION = "autonomy.execution"
    AUTONOMY_LEARNING = "autonomy.learning"
    AUTONOMY_AUDIT = "autonomy.audit"


@dataclass
class Span:
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    span_type: SpanType = SpanType.AUTONOMY_START
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"name": name, "timestamp": datetime.now(timezone.utc).isoformat(), "attributes": attributes or {}})

    def finish(self, status: str = "ok", attributes: Optional[Dict[str, Any]] = None) -> None:
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        if attributes:
            self.attributes.update(attributes)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id, "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id, "span_type": self.span_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "attributes": self.attributes, "events": self.events, "status": self.status,
        }


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    goal: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    spans: List[Span] = field(default_factory=list)

    def create_span(self, span_type: SpanType, parent_span_id: Optional[str] = None) -> Span:
        span = Span(trace_id=self.trace_id, parent_span_id=parent_span_id, span_type=span_type)
        self.spans.append(span)
        return span

    def finish(self) -> None:
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def timeline(self) -> List[Dict[str, Any]]:
        return sorted([s.as_dict() for s in self.spans], key=lambda s: s["start_time"])

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id, "goal": self.goal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "span_count": len(self.spans), "spans": self.timeline(),
        }


class AutonomyTelemetry:
    """Central telemetry collector for autonomous research workflows.

    Usage:
        telemetry = AutonomyTelemetry()
        trace = telemetry.start_trace(goal="Research AAPL momentum")
        span = trace.create_span(SpanType.AUTONOMY_RESEARCH)
        span.finish(status="ok")
        trace.finish()
    """

    def __init__(self, max_traces: int = 500) -> None:
        self._lock = threading.Lock()
        self._traces: Dict[str, Trace] = {}
        self._active_traces: Dict[str, Trace] = {}
        self._max_traces = max_traces
        self._initialized: bool = False
        logger.info("AutonomyTelemetry created (max_traces=%d)", max_traces)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AutonomyTelemetry initialized")

    async def shutdown(self) -> None:
        self._traces.clear()
        self._active_traces.clear()
        self._initialized = False
        logger.info("AutonomyTelemetry shutdown complete")

    def start_trace(self, goal: str = "") -> Trace:
        trace = Trace(goal=goal)
        with self._lock:
            self._active_traces[trace.trace_id] = trace
        return trace

    def finish_trace(self, trace: Trace) -> None:
        trace.finish()
        with self._lock:
            self._active_traces.pop(trace.trace_id, None)
            self._traces[trace.trace_id] = trace
            while len(self._traces) > self._max_traces:
                oldest = min(self._traces, key=lambda k: self._traces[k].start_time)
                del self._traces[oldest]

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            recent = sorted(self._traces.values(), key=lambda t: t.start_time, reverse=True)[:limit]
        return [t.as_dict() for t in recent]

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {"active_traces": len(self._active_traces), "archived_traces": len(self._traces)}

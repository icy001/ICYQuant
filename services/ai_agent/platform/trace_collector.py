"""Trace Collector — collects and aggregates distributed traces across the AI platform.

The TraceCollector aggregates traces from all platform subsystems (gateway,
control plane, model router, agents, tools) into a unified trace view for
end-to-end request visualization and performance analysis.

Trace aggregation:
    - Gateway -> ControlPlane -> ModelRouter -> Agent -> Tool
    - Full end-to-end latency breakdown
    - Error propagation tracking
    - Cross-component correlation
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceComponent(str, Enum):
    """Platform components that emit traces."""
    GATEWAY = "gateway"
    CONTROL_PLANE = "control_plane"
    MODEL_ROUTER = "model_router"
    AGENT = "agent"
    TOOL = "tool"
    GUARDRAIL = "guardrail"
    AUDIT = "audit"


@dataclass
class TraceSpan:
    """A single span within a trace."""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    component: TraceComponent = TraceComponent.GATEWAY
    operation: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    status: str = "running"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.monotonic()
        self.status = status


@dataclass
class CollectedTrace:
    """A complete trace with all spans."""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    request_id: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    spans: List[TraceSpan] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def span_count(self) -> int:
        return len(self.spans)

    def finish(self) -> None:
        self.end_time = time.monotonic()


class TraceCollector:
    """Collects and aggregates distributed traces across the AI platform.

    Provides end-to-end trace visualization and performance analysis
    by aggregating spans from all platform components.

    Usage:
        tc = TraceCollector()
        await tc.initialize()
        trace = tc.start_trace(request_id="req_1")
        span = tc.start_span(trace.trace_id, TraceComponent.MODEL_ROUTER, "route")
        tc.finish_span(span.span_id)
        tc.finish_trace(trace.trace_id)
    """

    def __init__(self, max_traces: int = 500) -> None:
        self._max_traces = max_traces
        self._active_traces: Dict[str, CollectedTrace] = {}
        self._completed_traces: List[CollectedTrace] = []
        self._active_spans: Dict[str, TraceSpan] = {}
        self._lock = threading.Lock()
        self._initialized: bool = False
        logger.info("TraceCollector created (max_traces=%d)", max_traces)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("TraceCollector initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._active_traces.clear()
            self._completed_traces.clear()
            self._active_spans.clear()
        self._initialized = False
        logger.info("TraceCollector shutdown complete")

    def start_trace(self, request_id: str = "") -> CollectedTrace:
        """Start a new trace for a request."""
        trace = CollectedTrace(request_id=request_id)
        with self._lock:
            self._active_traces[trace.trace_id] = trace
        logger.debug("TraceCollector: started trace %s", trace.trace_id)
        return trace

    def start_span(self, trace_id: str, component: TraceComponent, operation: str, parent_span_id: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None) -> Optional[TraceSpan]:
        """Start a new span within a trace."""
        with self._lock:
            if trace_id not in self._active_traces:
                return None
            span = TraceSpan(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                component=component,
                operation=operation,
                attributes=attributes or {},
            )
            self._active_spans[span.span_id] = span
            self._active_traces[trace_id].spans.append(span)
        return span

    def finish_span(self, span_id: str, status: str = "ok", attributes: Optional[Dict[str, Any]] = None) -> bool:
        """Finish a span."""
        with self._lock:
            span = self._active_spans.pop(span_id, None)
            if not span:
                return False
            span.finish(status)
            if attributes:
                span.attributes.update(attributes)
            return True

    def finish_trace(self, trace_id: str) -> bool:
        """Finish a trace and archive it."""
        with self._lock:
            trace = self._active_traces.pop(trace_id, None)
            if not trace:
                return False
            trace.finish()
            self._completed_traces.append(trace)
            if len(self._completed_traces) > self._max_traces:
                self._completed_traces = self._completed_traces[-self._max_traces:]
        logger.debug("TraceCollector: finished trace %s (%d spans)", trace_id, trace.span_count)
        return True

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID (from active or completed)."""
        with self._lock:
            trace = self._active_traces.get(trace_id)
            if not trace:
                for t in reversed(self._completed_traces):
                    if t.trace_id == trace_id:
                        trace = t
                        break
        if not trace:
            return None
        return self._trace_to_dict(trace)

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent completed traces."""
        with self._lock:
            recent = list(reversed(self._completed_traces[-limit:]))
        return [self._trace_to_dict(t) for t in recent]

    def _trace_to_dict(self, trace: CollectedTrace) -> Dict[str, Any]:
        return {
            "trace_id": trace.trace_id,
            "request_id": trace.request_id,
            "duration_ms": round(trace.duration_ms, 2) if trace.duration_ms else None,
            "span_count": trace.span_count,
            "spans": sorted([
                {
                    "span_id": s.span_id,
                    "component": s.component.value,
                    "operation": s.operation,
                    "duration_ms": round(s.duration_ms, 2) if s.duration_ms else None,
                    "status": s.status,
                    "attributes": s.attributes,
                }
                for s in trace.spans
            ], key=lambda x: x.get("duration_ms", 0) or 0, reverse=True),
        }

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._initialized,
                "active_traces": len(self._active_traces),
                "completed_traces": len(self._completed_traces),
                "active_spans": len(self._active_spans),
            }

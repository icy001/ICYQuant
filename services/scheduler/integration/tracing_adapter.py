"""Tracing Adapter — integrates the Scheduler with distributed tracing.

The :class:`TracingAdapter` enables distributed tracing across the
scheduler platform, propagating trace context through adapters.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceContext:
    """Distributed tracing context propagated across services."""

    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex[:32]
        self.span_id = span_id or uuid.uuid4().hex[:16]
        self.parent_span_id = parent_span_id
        self.baggage: Dict[str, str] = {}

    def child(self) -> "TraceContext":
        """Create a child span context."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.span_id,
        )

    def to_headers(self) -> Dict[str, str]:
        """Serialize to HTTP/gRPC headers (W3C Trace Context)."""
        return {
            "traceparent": f"00-{self.trace_id}-{self.span_id}-01",
            "tracestate": ",".join(f"{k}={v}" for k, v in self.baggage.items()),
        }

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TraceContext":
        """Parse from W3C Trace Context headers."""
        traceparent = headers.get("traceparent", "")
        parts = traceparent.split("-")
        trace_id = parts[1] if len(parts) > 1 else uuid.uuid4().hex[:32]
        span_id = parts[2] if len(parts) > 2 else uuid.uuid4().hex[:16]
        return cls(trace_id=trace_id, span_id=span_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }


class TracingAdapter:
    """Adapter for distributed tracing integration.

    Responsibilities:
    * Create and propagate trace contexts
    * Record spans for scheduler operations
    * Link scheduler traces with workflow traces
    * Export traces to the platform tracing backend

    Usage::

        adapter = TracingAdapter()
        ctx = adapter.start_trace("schedule_execution")
        # ... pass ctx through adapter chain ...
        adapter.end_trace(ctx)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connected = False
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        self._trace_count: int = 0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def trace_count(self) -> int:
        return self._trace_count

    async def connect(self) -> None:
        self._connected = True
        logger.info("TracingAdapter: connected")

    async def disconnect(self) -> None:
        self._connected = False
        self._active_traces.clear()

    async def synchronize(self) -> Dict[str, Any]:
        return {"active_traces": len(self._active_traces), "total_traces": self._trace_count}

    # ------------------------------------------------------------------
    # Trace Management
    # ------------------------------------------------------------------

    def start_trace(self, operation: str, parent: Optional[TraceContext] = None) -> TraceContext:
        """Start a new trace or child span."""
        with self._lock:
            self._trace_count += 1
            ctx = parent.child() if parent else TraceContext()
            self._active_traces[ctx.span_id] = {
                "operation": operation,
                "context": ctx,
                "started_at": datetime.now(timezone.utc),
            }
            return ctx

    def end_trace(self, ctx: TraceContext, status: str = "ok", attributes: Optional[Dict[str, Any]] = None) -> None:
        """End a trace span."""
        with self._lock:
            self._active_traces.pop(ctx.span_id, None)

    def inject(self, ctx: TraceContext) -> Dict[str, str]:
        """Inject trace context into outgoing request headers."""
        return ctx.to_headers()

    def extract(self, headers: Dict[str, str]) -> TraceContext:
        """Extract trace context from incoming request headers."""
        return TraceContext.from_headers(headers)

    def get_active_traces(self) -> List[Dict[str, Any]]:
        """Get all currently active traces."""
        with self._lock:
            return [
                {"operation": t["operation"], "trace_id": t["context"].trace_id, "span_id": t["context"].span_id}
                for t in self._active_traces.values()
            ]

"""
Platform Telemetry — Distributed tracing telemetry for the Strategy Platform.

Provides deployment, runtime, signal, order intent, and audit
timeline tracing for full pipeline observability.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TelemetrySpan:
    """A telemetry span representing a unit of work."""
    span_id: str
    trace_id: str
    name: str
    category: str  # deployment, runtime, signal, order_intent, audit
    parent_span_id: Optional[str] = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "ok"
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetryTrace:
    """A complete telemetry trace."""
    trace_id: str
    spans: list[TelemetrySpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"


class PlatformTelemetry:
    """
    Distributed telemetry for the Strategy Platform.

    Provides end-to-end tracing across the complete strategy
    pipeline: Deployment → Runtime → Signal → Order Intent → Audit.

    Usage::

        telemetry = PlatformTelemetry()
        await telemetry.initialize()

        # Start a trace
        trace = await telemetry.start_trace("strategy_deployment")
        span = await telemetry.start_span(trace.trace_id, "validate_package", "deployment")
        # ... work ...
        await telemetry.end_span(span.span_id)
        await telemetry.end_trace(trace.trace_id)
    """

    def __init__(self, max_traces: int = 5000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._spans: dict[str, TelemetrySpan] = {}
        self._max_traces = max_traces
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the telemetry system."""
        self._initialized = True
        logger.info("PlatformTelemetry initialized.")

    async def stop(self) -> None:
        """Stop the telemetry system."""
        self._initialized = False
        logger.info("PlatformTelemetry stopped.")

    # ---- Trace Operations ----

    async def start_trace(self, name: str) -> TelemetryTrace:
        """Start a new telemetry trace."""
        trace_id = str(uuid.uuid4())
        trace = TelemetryTrace(trace_id=trace_id)
        self._traces[trace_id] = trace

        # Trim if needed
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[:len(self._traces) - self._max_traces]
            for tid in oldest:
                self._traces.pop(tid, None)

        logger.debug(f"Telemetry trace started: {trace_id} ({name})")
        return trace

    async def end_trace(self, trace_id: str, status: str = "ok") -> Optional[TelemetryTrace]:
        """End a telemetry trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.completed_at = datetime.now(timezone.utc)
            trace.status = status
        return trace

    async def start_span(
        self,
        trace_id: str,
        name: str,
        category: str,
        tags: Optional[dict[str, str]] = None,
        parent_span_id: Optional[str] = None,
    ) -> TelemetrySpan:
        """Start a telemetry span."""
        span_id = str(uuid.uuid4())

        span = TelemetrySpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            category=category,
            parent_span_id=parent_span_id,
            tags=tags or {},
        )
        self._spans[span_id] = span

        # Add to trace
        trace = self._traces.get(trace_id)
        if trace:
            trace.spans.append(span)

        return span

    async def end_span(
        self,
        span_id: str,
        status: str = "ok",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[TelemetrySpan]:
        """End a telemetry span."""
        span = self._spans.get(span_id)
        if not span:
            return None

        span.ended_at = time.monotonic()
        span.duration_ms = (span.ended_at - span.started_at) * 1000
        span.status = status
        if metadata:
            span.metadata.update(metadata)

        return span

    # ---- Category-Specific Spans ----

    async def trace_deployment(
        self,
        strategy_id: str,
        version: str,
        callback: Any,
    ) -> dict[str, Any]:
        """Trace a deployment operation."""
        trace = await self.start_trace(f"deployment.{strategy_id}")
        span = await self.start_span(
            trace.trace_id, f"deploy_{strategy_id}", "deployment",
            tags={"strategy_id": strategy_id, "version": version},
        )

        try:
            result = await callback() if asyncio.iscoroutinefunction(callback) else callback()
            await self.end_span(span.span_id, "ok", {"result": "success"})
            await self.end_trace(trace.trace_id, "ok")
            return {"success": True, "trace_id": trace.trace_id}
        except Exception as e:
            await self.end_span(span.span_id, "error", {"error": str(e)})
            await self.end_trace(trace.trace_id, "error")
            return {"success": False, "trace_id": trace.trace_id, "error": str(e)}

    async def trace_runtime(
        self,
        strategy_id: str,
        callback: Any,
    ) -> dict[str, Any]:
        """Trace a runtime operation."""
        trace = await self.start_trace(f"runtime.{strategy_id}")
        span = await self.start_span(
            trace.trace_id, f"run_{strategy_id}", "runtime",
            tags={"strategy_id": strategy_id},
        )

        try:
            result = await callback() if asyncio.iscoroutinefunction(callback) else callback()
            await self.end_span(span.span_id, "ok")
            await self.end_trace(trace.trace_id, "ok")
            return {"success": True, "trace_id": trace.trace_id}
        except Exception as e:
            await self.end_span(span.span_id, "error", {"error": str(e)})
            await self.end_trace(trace.trace_id, "error")
            return {"success": False, "trace_id": trace.trace_id, "error": str(e)}

    async def trace_signal(self, strategy_id: str, callback: Any) -> dict[str, Any]:
        """Trace a signal generation operation."""
        trace = await self.start_trace(f"signal.{strategy_id}")
        span = await self.start_span(
            trace.trace_id, f"signal_{strategy_id}", "signal",
            tags={"strategy_id": strategy_id},
        )

        try:
            result = await callback() if asyncio.iscoroutinefunction(callback) else callback()
            await self.end_span(span.span_id, "ok")
            await self.end_trace(trace.trace_id, "ok")
            return {"success": True, "trace_id": trace.trace_id}
        except Exception as e:
            await self.end_span(span.span_id, "error", {"error": str(e)})
            await self.end_trace(trace.trace_id, "error")
            return {"success": False, "trace_id": trace.trace_id, "error": str(e)}

    # ---- Retrieval ----

    async def get_trace(self, trace_id: str) -> Optional[TelemetryTrace]:
        """Get a telemetry trace."""
        return self._traces.get(trace_id)

    async def get_span(self, span_id: str) -> Optional[TelemetrySpan]:
        """Get a telemetry span."""
        return self._spans.get(span_id)

    async def get_trace_summary(self, trace_id: str) -> Optional[dict[str, Any]]:
        """Get a summary of a telemetry trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            return None

        total_duration = sum(s.duration_ms for s in trace.spans)
        errors = [s for s in trace.spans if s.status == "error"]
        categories: dict[str, int] = {}
        for s in trace.spans:
            categories[s.category] = categories.get(s.category, 0) + 1

        return {
            "trace_id": trace_id,
            "span_count": len(trace.spans),
            "total_duration_ms": total_duration,
            "error_count": len(errors),
            "status": trace.status,
            "categories": categories,
        }

    async def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent traces."""
        return [
            {"trace_id": tid, "status": t.status, "spans": len(t.spans)}
            for tid, t in list(self._traces.items())[-limit:]
        ]

    async def health_check(self) -> dict[str, Any]:
        """Check telemetry health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_traces": len(self._traces),
            "active_spans": len(self._spans),
            "max_traces": self._max_traces,
        }

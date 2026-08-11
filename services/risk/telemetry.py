"""
Risk Telemetry — Distributed tracing for the Risk Platform.

Provides end-to-end telemetry across Risk Timeline, Policy Timeline,
Evaluation Timeline, Approval Timeline, and Audit Trail.
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
    """A telemetry span in the risk pipeline."""
    span_id: str
    trace_id: str
    name: str
    category: str  # risk, policy, evaluation, approval, audit
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


class RiskTelemetry:
    """
    Distributed telemetry for the Risk Management Platform.

    Provides end-to-end tracing across:
        Risk Timeline → Policy Timeline → Evaluation Timeline
        → Approval Timeline → Audit Trail

    Usage::

        telemetry = RiskTelemetry()
        await telemetry.initialize()

        trace = await telemetry.start_trace("risk_evaluation")
        span = await telemetry.start_span(trace.trace_id, "check_position", "evaluation")
        await telemetry.end_span(span.span_id)
        await telemetry.end_trace(trace.trace_id)
    """

    def __init__(self, max_traces: int = 5000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._spans: dict[str, TelemetrySpan] = {}
        self._max_traces = max_traces

    async def initialize(self) -> None:
        logger.info("RiskTelemetry initialized.")

    async def stop(self) -> None:
        logger.info("RiskTelemetry stopped.")

    # ---- Trace Operations ----

    async def start_trace(self, name: str) -> TelemetryTrace:
        trace_id = str(uuid.uuid4())
        trace = TelemetryTrace(trace_id=trace_id)
        self._traces[trace_id] = trace
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[:len(self._traces) - self._max_traces]
            for tid in oldest:
                self._traces.pop(tid, None)
        return trace

    async def end_trace(self, trace_id: str, status: str = "ok") -> Optional[TelemetryTrace]:
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
        span = self._spans.get(span_id)
        if not span:
            return None
        span.ended_at = time.monotonic()
        span.duration_ms = (span.ended_at - span.started_at) * 1000
        span.status = status
        if metadata:
            span.metadata.update(metadata)
        return span

    # ---- Category-Specific Methods ----

    async def trace_risk_evaluation(
        self,
        request_id: str,
        callback: Any,
    ) -> dict[str, Any]:
        """Trace a complete risk evaluation."""
        trace = await self.start_trace(f"risk_eval.{request_id}")
        span = await self.start_span(trace.trace_id, f"evaluate_{request_id}", "evaluation")
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
        return self._traces.get(trace_id)

    async def get_span(self, span_id: str) -> Optional[TelemetrySpan]:
        return self._spans.get(span_id)

    async def get_trace_summary(self, trace_id: str) -> Optional[dict[str, Any]]:
        trace = self._traces.get(trace_id)
        if not trace:
            return None
        total_duration = sum(s.duration_ms for s in trace.spans)
        errors = [s for s in trace.spans if s.status == "error"]
        return {
            "trace_id": trace_id,
            "span_count": len(trace.spans),
            "total_duration_ms": total_duration,
            "error_count": len(errors),
            "status": "error" if errors else trace.status,
        }

    async def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {"trace_id": tid, "status": t.status, "spans": len(t.spans)}
            for tid, t in list(self._traces.items())[-limit:]
        ]

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "active_traces": len(self._traces),
            "active_spans": len(self._spans),
        }

"""
Portfolio Telemetry — Distributed tracing for the portfolio risk pipeline.

Provides structured tracing spans for portfolio evaluation, PnL
computation, exposure updates, alert generation, and risk actions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TelemetryPhase(str, Enum):
    """Portfolio risk pipeline phases."""
    SNAPSHOT = "SNAPSHOT"
    PNL_UPDATE = "PNL_UPDATE"
    EXPOSURE_UPDATE = "EXPOSURE_UPDATE"
    MARGIN_CHECK = "MARGIN_CHECK"
    DRAWDOWN_CHECK = "DRAWDOWN_CHECK"
    CONCENTRATION_CHECK = "CONCENTRATION_CHECK"
    GREEKS_COMPUTE = "GREEKS_COMPUTE"
    FACTOR_COMPUTE = "FACTOR_COMPUTE"
    CORRELATION_COMPUTE = "CORRELATION_COMPUTE"
    LIQUIDITY_CHECK = "LIQUIDITY_CHECK"
    ALERT_GENERATION = "ALERT_GENERATION"
    ALERT_DISPATCH = "ALERT_DISPATCH"
    ACTION_GENERATION = "ACTION_GENERATION"
    ACTION_EXECUTION = "ACTION_EXECUTION"
    KILL_SWITCH = "KILL_SWITCH"
    HEDGE_EVALUATION = "HEDGE_EVALUATION"
    STRATEGY_PAUSE = "STRATEGY_PAUSE"
    INTRADAY_CHECK = "INTRADAY_CHECK"


@dataclass
class TelemetrySpan:
    """A single telemetry span."""
    span_id: str
    phase: TelemetryPhase
    account_id: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_span_id: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.ended_at > 0


@dataclass
class TelemetryTrace:
    """A complete trace spanning multiple pipeline phases."""
    trace_id: str
    account_id: str = ""
    snapshot_id: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    total_duration_ms: float = 0.0
    spans: list[TelemetrySpan] = field(default_factory=list)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def span_count(self) -> int:
        return len(self.spans)


class PortfolioTelemetry:
    """
    Distributed tracing for the portfolio risk pipeline.

    Provides structured tracing spans for each phase of portfolio
    risk evaluation, PnL computation, alert generation, and risk
    action execution.

    Usage::

        telemetry = PortfolioTelemetry()

        trace = telemetry.start_trace("ACC-01", snapshot_id="SNAP-001")
        span = telemetry.start_span(TelemetryPhase.PNL_UPDATE, trace.trace_id)
        # ... do work ...
        telemetry.end_span(span, success=True)
        telemetry.end_trace(trace)
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._trace_history: list[TelemetryTrace] = []
        self._max_traces = max_traces
        self._span_counter: int = 0
        self._trace_counter: int = 0

    # ---- Trace Management ----

    def start_trace(
        self,
        account_id: str = "",
        snapshot_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> TelemetryTrace:
        """Start a new telemetry trace."""
        self._trace_counter += 1
        trace_id = f"TRACE-{self._trace_counter:08d}"

        trace = TelemetryTrace(
            trace_id=trace_id,
            account_id=account_id,
            snapshot_id=snapshot_id,
            started_at=time.perf_counter(),
            metadata=metadata or {},
        )

        self._traces[trace_id] = trace
        return trace

    def end_trace(self, trace: TelemetryTrace, success: bool = True) -> TelemetryTrace:
        """End a telemetry trace."""
        trace.ended_at = time.perf_counter()
        trace.total_duration_ms = (trace.ended_at - trace.started_at) * 1000
        trace.success = success

        # Archive
        self._trace_history.append(trace)
        self._traces.pop(trace.trace_id, None)

        # Trim history
        if len(self._trace_history) > self._max_traces:
            self._trace_history = self._trace_history[-self._max_traces:]

        logger.debug(
            f"Trace {trace.trace_id}: {trace.total_duration_ms:.1f}ms, "
            f"{trace.span_count} spans, success={success}"
        )
        return trace

    # ---- Span Management ----

    def start_span(
        self,
        phase: TelemetryPhase,
        account_id: str = "",
        parent_span_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Start a new span within a trace."""
        self._span_counter += 1
        span_id = f"SPAN-{self._span_counter:08d}"

        return TelemetrySpan(
            span_id=span_id,
            phase=phase,
            account_id=account_id,
            started_at=time.perf_counter(),
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )

    def end_span(
        self,
        span: TelemetrySpan,
        success: bool = True,
        error_message: str = "",
        attributes: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """End a telemetry span."""
        span.ended_at = time.perf_counter()
        span.duration_ms = (span.ended_at - span.started_at) * 1000
        span.success = success
        span.error_message = error_message

        if attributes:
            span.attributes.update(attributes)

        if not success:
            logger.warning(
                f"Span {span.span_id} [{span.phase.value}]: FAILED "
                f"({span.duration_ms:.1f}ms) — {error_message}"
            )

        return span

    # ---- Async Context Manager ----

    class SpanContext:
        """Async context manager for automatic span timing."""

        def __init__(
            self,
            telemetry: PortfolioTelemetry,
            phase: TelemetryPhase,
            account_id: str = "",
        ) -> None:
            self._telemetry = telemetry
            self._phase = phase
            self._account_id = account_id
            self.span: Optional[TelemetrySpan] = None

        async def __aenter__(self) -> TelemetrySpan:
            self.span = self._telemetry.start_span(
                self._phase, self._account_id
            )
            return self.span

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            if self.span:
                self._telemetry.end_span(
                    self.span,
                    success=exc_type is None,
                    error_message=str(exc_val) if exc_val else "",
                )

    def span(self, phase: TelemetryPhase, account_id: str = "") -> SpanContext:
        """Create an async context manager for automatic span timing."""
        return self.SpanContext(self, phase, account_id)

    # ---- Query ----

    def get_trace(self, trace_id: str) -> Optional[TelemetryTrace]:
        """Get a specific trace."""
        return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 20) -> list[TelemetryTrace]:
        """Get recent completed traces."""
        return self._trace_history[-limit:]

    def get_timeline(self, account_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
        """Get a timeline of recent span events."""
        events = []
        for trace in self._trace_history[-limit:]:
            if account_id and trace.account_id != account_id:
                continue
            for span in trace.spans:
                events.append({
                    "trace_id": trace.trace_id,
                    "span_id": span.span_id,
                    "phase": span.phase.value,
                    "duration_ms": span.duration_ms,
                    "success": span.success,
                    "account_id": span.account_id,
                })
        return events

    def get_stats(self) -> dict[str, Any]:
        """Get telemetry statistics."""
        total_spans = sum(t.span_count for t in self._trace_history)
        total_traces = len(self._trace_history)
        avg_duration = (
            sum(t.total_duration_ms for t in self._trace_history) / total_traces
            if total_traces > 0 else 0
        )

        return {
            "total_traces": total_traces,
            "total_spans": total_spans,
            "avg_trace_duration_ms": avg_duration,
            "active_traces": len(self._traces),
        }

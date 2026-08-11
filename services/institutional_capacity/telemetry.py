"""
Capacity Telemetry — End-to-end tracing for capacity operations.

Traces the lifecycle of capital through the capacity pipeline:
    Strategy → Liquidity → Impact → Execution → Result

Enables observability of where capacity is consumed, constrained, or rejected.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TraceState(str, Enum):
    STARTED = "started"
    CAPACITY_CHECK = "capacity_check"
    LIQUIDITY_CHECK = "liquidity_check"
    IMPACT_CHECK = "impact_check"
    EXECUTION_CHECK = "execution_check"
    GUARD_CHECK = "guard_check"
    DECISION = "decision"
    EXECUTING = "executing"
    COMPLETED = "completed"
    RESIZED = "resized"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ERROR = "error"


@dataclass
class TraceSpan:
    """A single span in a capacity trace."""

    span_id: str = field(default_factory=lambda: f"TS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    state: TraceState = TraceState.STARTED
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0

    data: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    is_error: bool = False
    error_message: str = ""

    def finish(self) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "name": self.name,
            "state": self.state.value,
            "duration_ms": round(self.duration_ms, 2),
            "is_error": self.is_error,
            "data": self.data,
        }


@dataclass
class CapacityTrace:
    """Complete end-to-end trace of a capacity operation."""

    trace_id: str = field(default_factory=lambda: f"CT-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""
    operation: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    spans: List[TraceSpan] = field(default_factory=list)
    current_state: TraceState = TraceState.STARTED

    # Result
    final_state: TraceState = TraceState.COMPLETED
    final_amount: float = 0.0
    total_duration_ms: float = 0.0
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "operation": self.operation,
            "current_state": self.current_state.value,
            "final_state": self.final_state.value,
            "final_amount": self.final_amount,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "is_error": self.is_error,
        }


class CapacityTelemetry:
    """End-to-end telemetry for capacity operations.

    Traces: Strategy → Liquidity → Impact → Execution → Guard → Decision → Result
    """

    def __init__(self):
        self._traces: Dict[str, CapacityTrace] = {}
        self._active_traces: Dict[str, CapacityTrace] = {}
        self._max_traces: int = 1000

    # ── Trace Lifecycle ───────────────────────────────────────────

    def start_trace(self,
                    strategy_id: str,
                    asset: str,
                    operation: str = "capacity_assess") -> CapacityTrace:
        """Begin a new capacity trace."""
        trace = CapacityTrace(
            strategy_id=strategy_id,
            asset=asset,
            operation=operation,
        )
        self._active_traces[trace.trace_id] = trace
        return trace

    def add_span(self,
                 trace_id: str,
                 name: str,
                 state: TraceState,
                 data: Optional[Dict[str, Any]] = None,
                 tags: Optional[Dict[str, str]] = None,
                 is_error: bool = False,
                 error_message: str = "") -> Optional[TraceSpan]:
        """Add a span to an active trace."""
        trace = self._active_traces.get(trace_id)
        if trace is None:
            return None

        span = TraceSpan(
            name=name,
            state=state,
            data=data or {},
            tags=tags or {},
            is_error=is_error,
            error_message=error_message,
        )
        span.finish()
        trace.spans.append(span)
        trace.current_state = state

        if is_error:
            trace.is_error = True

        return span

    def finish_trace(self,
                      trace_id: str,
                      final_state: TraceState,
                      final_amount: float = 0.0,
                      is_error: bool = False) -> Optional[CapacityTrace]:
        """End a trace and archive it."""
        trace = self._active_traces.pop(trace_id, None)
        if trace is None:
            return None

        trace.final_state = final_state
        trace.final_amount = final_amount
        trace.total_duration_ms = (
            (datetime.now(timezone.utc) - trace.started_at).total_seconds() * 1000
        )
        trace.is_error = trace.is_error or is_error
        trace.current_state = final_state

        self._traces[trace.trace_id] = trace
        self._prune()
        return trace

    # ── Convenience Methods ───────────────────────────────────────

    def trace_assessment(self,
                          strategy_id: str,
                          asset: str,
                          requested_amount: float,
                          executable_amount: float,
                          liquidity_score: float,
                          expected_impact_bps: float,
                          state: TraceState,
                          duration_ms: float = 0.0) -> CapacityTrace:
        """Trace a complete capacity assessment."""
        trace = self.start_trace(strategy_id, asset, "capacity_assess")

        self.add_span(trace.trace_id, "capacity_check", TraceState.CAPACITY_CHECK, {
            "requested_amount": requested_amount,
        })
        self.add_span(trace.trace_id, "liquidity_check", TraceState.LIQUIDITY_CHECK, {
            "liquidity_score": liquidity_score,
        })
        self.add_span(trace.trace_id, "impact_check", TraceState.IMPACT_CHECK, {
            "expected_impact_bps": expected_impact_bps,
        })

        return self.finish_trace(
            trace.trace_id,
            state,
            final_amount=executable_amount,
        ) or trace

    def trace_decision(self,
                        strategy_id: str,
                        asset: str,
                        requested_amount: float,
                        decision_type: str,
                        approved_amount: float,
                        reason: str = "") -> CapacityTrace:
        """Trace a capacity decision."""
        trace = self.start_trace(strategy_id, asset, "capacity_decide")

        state_map = {
            "proceed": TraceState.COMPLETED,
            "resize": TraceState.RESIZED,
            "split": TraceState.COMPLETED,
            "defer": TraceState.DEFERRED,
            "reject": TraceState.REJECTED,
        }
        final_state = state_map.get(decision_type, TraceState.COMPLETED)

        self.add_span(trace.trace_id, "decision", TraceState.DECISION, {
            "decision_type": decision_type,
            "requested_amount": requested_amount,
            "approved_amount": approved_amount,
            "reason": reason,
        })

        return self.finish_trace(
            trace.trace_id,
            final_state,
            final_amount=approved_amount,
        ) or trace

    def trace_execution(self,
                         strategy_id: str,
                         asset: str,
                         order_amount: float,
                         executed_amount: float,
                         impact_bps: float,
                         duration_seconds: float) -> CapacityTrace:
        """Trace a complete execution."""
        trace = self.start_trace(strategy_id, asset, "capacity_execute")

        self.add_span(trace.trace_id, "guard_check", TraceState.GUARD_CHECK, {
            "order_amount": order_amount,
        })
        self.add_span(trace.trace_id, "executing", TraceState.EXECUTING, {
            "executed_amount": executed_amount,
            "impact_bps": impact_bps,
            "duration_seconds": duration_seconds,
        })

        final_state = (
            TraceState.COMPLETED if executed_amount > 0
            else TraceState.REJECTED
        )

        return self.finish_trace(
            trace.trace_id,
            final_state,
            final_amount=executed_amount,
        ) or trace

    # ── Queries ───────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> Optional[CapacityTrace]:
        return self._traces.get(trace_id)

    def recent_traces(self, limit: int = 50) -> List[CapacityTrace]:
        traces = list(self._traces.values())
        traces.sort(key=lambda t: t.started_at, reverse=True)
        return traces[:limit]

    def traces_by_strategy(self, strategy_id: str) -> List[CapacityTrace]:
        return [t for t in self._traces.values() if t.strategy_id == strategy_id]

    def traces_by_asset(self, asset: str) -> List[CapacityTrace]:
        return [t for t in self._traces.values() if t.asset == asset]

    def error_traces(self) -> List[CapacityTrace]:
        return [t for t in self._traces.values() if t.is_error]

    def rejected_traces(self) -> List[CapacityTrace]:
        return [t for t in self._traces.values()
                if t.final_state == TraceState.REJECTED]

    def avg_duration_ms(self) -> float:
        if not self._traces:
            return 0.0
        return sum(t.total_duration_ms for t in self._traces.values()) / len(self._traces)

    def p95_duration_ms(self) -> float:
        durations = sorted(t.total_duration_ms for t in self._traces.values())
        if not durations:
            return 0.0
        idx = int(len(durations) * 0.95)
        return durations[idx]

    def active_count(self) -> int:
        return len(self._active_traces)

    def total_count(self) -> int:
        return len(self._traces)

    # ── Utility ───────────────────────────────────────────────────

    def _prune(self) -> None:
        while len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.values(), key=lambda t: t.started_at)[0]
            self._traces.pop(oldest.trace_id, None)

    def clear(self) -> None:
        self._traces.clear()
        self._active_traces.clear()

    def summary(self) -> Dict[str, Any]:
        traces = list(self._traces.values())
        return {
            "total_traces": self.total_count(),
            "active_traces": self.active_count(),
            "error_traces": len(self.error_traces()),
            "rejected_traces": len(self.rejected_traces()),
            "avg_duration_ms": round(self.avg_duration_ms(), 2),
            "p95_duration_ms": round(self.p95_duration_ms(), 2),
            "by_state": {
                state.value: len([t for t in traces if t.final_state == state])
                for state in TraceState
            },
        }

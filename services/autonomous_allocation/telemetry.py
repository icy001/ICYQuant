"""Allocation Telemetry — end-to-end trace of allocation decisions.

Every autonomous allocation decision generates a complete trace:
capital_state → strategy_state → alpha → risk → capacity →
liquidity → impact → stress → survival → allocation_score →
target_allocation → guard → rebalance_plan → execution →
realized_result → feedback

This enables answering:
- Why was capital increased/decreased?
- By how much?
- Why not more/less?
- Why was execution rejected/deferred?
- What was the realized outcome?
- How accurate were the predictions?
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TelemetrySpan:
    """A single span in the allocation telemetry trace."""
    span_name: str
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "STARTED"
    data: Dict[str, Any] = field(default_factory=dict)
    parent_span_id: str = ""
    span_id: str = ""

    def __post_init__(self):
        if not self.span_id:
            ts = self.start_time.strftime("%Y%m%d%H%M%S%f")
            self.span_id = f"span-{ts}-{hash(self.span_name) & 0xFFFF:04x}"

    def finish(self, status: str = "OK", data: Optional[Dict[str, Any]] = None) -> None:
        """Mark this span as complete."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        if data:
            self.data.update(data)


@dataclass
class AllocationTrace:
    """Complete allocation decision trace."""
    trace_id: str = ""
    strategy_id: str = ""
    decision_id: str = ""
    spans: List[TelemetrySpan] = field(default_factory=list)
    root_span: Optional[TelemetrySpan] = None
    status: str = "INITIATED"
    total_duration_ms: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    def __post_init__(self):
        if not self.trace_id:
            ts = self.start_time.strftime("%Y%m%d%H%M%S%f")
            self.trace_id = f"trace-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"

    def finish(self, status: str = "COMPLETE") -> None:
        """Mark the complete trace as finished."""
        self.end_time = datetime.utcnow()
        self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for export."""
        return {
            "trace_id": self.trace_id,
            "strategy_id": self.strategy_id,
            "decision_id": self.decision_id,
            "status": self.status,
            "total_duration_ms": self.total_duration_ms,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "spans": [
                {
                    "span_name": s.span_name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "data": s.data,
                }
                for s in self.spans
            ],
        }


class AllocationTelemetry:
    """End-to-end telemetry for autonomous allocation.

    Traces every allocation decision from inception to feedback.
    """

    def __init__(self, max_traces: int = 10000):
        self._traces: Dict[str, AllocationTrace] = {}
        self._max_traces = max_traces
        self._active_traces: Dict[str, AllocationTrace] = {}

    def start_trace(self, strategy_id: str,
                    decision_id: str = "") -> AllocationTrace:
        """Start a new allocation trace."""
        trace = AllocationTrace(
            strategy_id=strategy_id,
            decision_id=decision_id,
        )
        self._active_traces[trace.trace_id] = trace
        return trace

    def add_span(self, trace: AllocationTrace, span_name: str,
                 parent_span: Optional[TelemetrySpan] = None) -> TelemetrySpan:
        """Add a span to an existing trace."""
        span = TelemetrySpan(
            span_name=span_name,
            parent_span_id=parent_span.span_id if parent_span else "",
        )
        trace.spans.append(span)
        return span

    def finish_trace(self, trace: AllocationTrace,
                     status: str = "COMPLETE") -> None:
        """Finish a trace and archive it."""
        trace.finish(status)

        # Finish any unfinished spans
        for span in trace.spans:
            if span.end_time is None:
                span.finish("INCOMPLETE")

        # Archive
        if trace.trace_id in self._active_traces:
            del self._active_traces[trace.trace_id]

        self._traces[trace.trace_id] = trace

        # Enforce max traces
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[0]
            del self._traces[oldest]

    def get_trace(self, trace_id: str) -> Optional[AllocationTrace]:
        """Retrieve a trace by ID."""
        return self._traces.get(trace_id) or self._active_traces.get(trace_id)

    def recent_traces(self, n: int = 10) -> List[AllocationTrace]:
        """Get recent completed traces."""
        traces = list(self._traces.values())
        traces.sort(key=lambda t: t.start_time, reverse=True)
        return traces[:n]

    def get_strategy_traces(self, strategy_id: str,
                            limit: int = 50) -> List[AllocationTrace]:
        """Get traces for a specific strategy."""
        traces = [
            t for t in self._traces.values()
            if t.strategy_id == strategy_id
        ]
        traces.sort(key=lambda t: t.start_time, reverse=True)
        return traces[:limit]

    def build_standard_trace(self, strategy_id: str,
                              scores: Dict[str, float],
                              marginal: Dict[str, float],
                              decision: Dict[str, Any],
                              result: Dict[str, Any]) -> AllocationTrace:
        """Build a standard trace with all standard spans."""
        trace = self.start_trace(strategy_id, decision.get("decision_id", ""))

        # Capital state span
        cap_span = self.add_span(trace, "capital_state")
        cap_span.finish("OK", {"total_capital": scores.get("total_capital", 0)})

        # Strategy state span
        strat_span = self.add_span(trace, "strategy_state")
        strat_span.finish("OK", scores)

        # Alpha estimate
        alpha_span = self.add_span(trace, "alpha_estimate")
        alpha_span.finish("OK", {"alpha_score": scores.get("alpha_score", 0)})

        # Risk estimate
        risk_span = self.add_span(trace, "risk_estimate")
        risk_span.finish("OK", {"risk_score": scores.get("risk_score", 0)})

        # Capacity estimate
        cap_span2 = self.add_span(trace, "capacity_estimate")
        cap_span2.finish("OK", {"capacity_score": scores.get("capacity_score", 0)})

        # Liquidity estimate
        liq_span = self.add_span(trace, "liquidity_estimate")
        liq_span.finish("OK", {"liquidity_score": scores.get("liquidity_score", 0)})

        # Impact estimate
        imp_span = self.add_span(trace, "impact_estimate")
        imp_span.finish("OK", {"impact_score": scores.get("impact_score", 0)})

        # Stress estimate
        stress_span = self.add_span(trace, "stress_estimate")
        stress_span.finish("OK", {"stress_score": scores.get("stress_score", 0)})

        # Survival estimate
        surv_span = self.add_span(trace, "survival_estimate")
        surv_span.finish("OK", {"survival_score": scores.get("survival_score", 0)})

        # Allocation score
        score_span = self.add_span(trace, "allocation_score")
        score_span.finish("OK", {"composite_score": scores.get("composite_score", 0)})

        # Target allocation
        target_span = self.add_span(trace, "target_allocation")
        target_span.finish("OK", decision)

        # Guard check
        guard_span = self.add_span(trace, "allocation_guard")
        guard_span.finish("OK", {"guard_result": decision.get("guard_result", "PENDING")})

        # Rebalance plan
        reb_span = self.add_span(trace, "rebalance_plan")
        reb_span.finish("OK")

        # Execution
        exec_span = self.add_span(trace, "execution")
        exec_span.finish("OK", result.get("execution", {}))

        # Realized result
        realized_span = self.add_span(trace, "realized_result")
        realized_span.finish("OK", result)

        # Feedback
        fb_span = self.add_span(trace, "feedback")
        fb_span.finish("OK")
        self.finish_trace(trace)
        return trace

"""
Governance Telemetry — decision trace and observability.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionTrace:
    """A complete trace of a single governance decision pipeline."""

    trace_id: str
    decision_id: str = ""
    request_id: str = ""

    # Trace segments
    decision_request: Dict[str, Any] = field(default_factory=dict)
    decision_context: Dict[str, Any] = field(default_factory=dict)
    policy_evaluation: Dict[str, Any] = field(default_factory=dict)
    authority_evaluation: Dict[str, Any] = field(default_factory=dict)
    constraint_evaluation: Dict[str, Any] = field(default_factory=dict)
    approval_evaluation: Dict[str, Any] = field(default_factory=dict)
    decision_guard: Dict[str, Any] = field(default_factory=dict)
    final_decision: Dict[str, Any] = field(default_factory=dict)
    execution_reference: Dict[str, Any] = field(default_factory=dict)

    # IDs for correlation
    policy_ids: List[str] = field(default_factory=list)
    authority_ids: List[str] = field(default_factory=list)
    approval_ids: List[str] = field(default_factory=list)

    # Timing breakdown
    timings: Dict[str, float] = field(default_factory=dict)
    total_latency_ms: float = 0.0

    @property
    def is_complete(self) -> bool:
        return bool(self.final_decision)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "segments": {
                "request": self.decision_request,
                "context": self.decision_context,
                "policy": self.policy_evaluation,
                "authority": self.authority_evaluation,
                "constraint": self.constraint_evaluation,
                "approval": self.approval_evaluation,
                "guard": self.decision_guard,
                "final": self.final_decision,
                "execution": self.execution_reference,
            },
            "correlation_ids": {
                "policy_ids": self.policy_ids,
                "authority_ids": self.authority_ids,
                "approval_ids": self.approval_ids,
            },
            "timings": self.timings,
            "total_latency_ms": self.total_latency_ms,
        }


class GovernanceTelemetry:
    """
    Collects and exports governance telemetry data.
    Provides per-decision traces for debugging and compliance.
    """

    def __init__(self, max_traces: int = 10000):
        self._traces: Dict[str, DecisionTrace] = {}
        self._max_traces = max_traces

    # ------------------------------------------------------------------
    # Trace management
    # ------------------------------------------------------------------

    def start_trace(self, trace_id: str, request_id: str, decision_id: str = "") -> DecisionTrace:
        """Start a new decision trace."""
        trace = DecisionTrace(
            trace_id=trace_id,
            request_id=request_id,
            decision_id=decision_id,
        )
        self._traces[trace_id] = trace
        self._prune()
        return trace

    def get_trace(self, trace_id: str) -> Optional[DecisionTrace]:
        return self._traces.get(trace_id)

    def record_segment(
        self,
        trace_id: str,
        segment: str,
        data: Dict[str, Any],
        latency_ms: float = 0.0,
    ) -> None:
        """Record a segment of the decision trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            return

        setattr(trace, segment, data)
        trace.timings[segment] = latency_ms

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_recent_traces(self, n: int = 20) -> List[Dict[str, Any]]:
        traces = list(self._traces.values())
        traces.sort(key=lambda t: t.total_latency_ms, reverse=True)
        return [t.to_dict() for t in traces[:n]]

    def get_traces_by_decision(self, decision_id: str) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._traces.values()
                if t.decision_id == decision_id]

    def get_slow_traces(self, threshold_ms: float = 100.0) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._traces.values()
                if t.total_latency_ms > threshold_ms]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._traces)

    def avg_latency(self) -> float:
        traces = list(self._traces.values())
        if not traces:
            return 0.0
        return sum(t.total_latency_ms for t in traces) / len(traces)

    def get_breakdown(self) -> Dict[str, Any]:
        """Average timing breakdown across all traces."""
        traces = list(self._traces.values())
        if not traces:
            return {}

        segment_times: Dict[str, List[float]] = {}
        for t in traces:
            for seg, lat in t.timings.items():
                if seg not in segment_times:
                    segment_times[seg] = []
                segment_times[seg].append(lat)

        return {
            seg: sum(times) / len(times)
            for seg, times in segment_times.items()
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        if len(self._traces) > self._max_traces:
            # Remove oldest half
            keys = list(self._traces.keys())
            for k in keys[:len(keys) // 2]:
                del self._traces[k]

    def clear(self) -> None:
        self._traces.clear()

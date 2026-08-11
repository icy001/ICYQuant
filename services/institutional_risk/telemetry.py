"""RiskTelemetry — risk decision tracing and audit.

Creates complete trace of every risk decision:
    Capital State → Portfolio State → Risk State →
    Stress → Survival → Budget → Action → Result

Enables answering: "Why was this action taken?"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class TraceSpan(Enum):
    """Trace span types for risk decisions."""

    CAPITAL_STATE = auto()
    PORTFOLIO_STATE = auto()
    RISK_STATE = auto()
    STRESS_SCENARIO = auto()
    STRESS_RESULT = auto()
    SURVIVAL_SCORE = auto()
    RISK_BUDGET = auto()
    RISK_ACTION = auto()
    CAPITAL_REALLOCATION = auto()
    POST_ACTION_STRESS = auto()
    EXECUTION = auto()
    FEEDBACK = auto()


@dataclass
class TraceEvent:
    """A single event in the trace."""

    span: TraceSpan
    trace_id: str
    timestamp: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    parent_span: Optional[TraceSpan] = None


@dataclass
class RiskDecisionTrace:
    """Complete trace of a risk decision."""

    trace_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    events: List[TraceEvent] = field(default_factory=list)
    decision_summary: str = ""
    pre_action_survival: float = 100.0
    post_action_survival: float = 100.0
    stress_survival: float = 100.0
    action_taken: str = ""
    outcome: str = ""


class RiskTelemetry:
    """Telemetry and tracing for risk decisions.

    Every risk decision produces a complete, auditable trace
    showing the full decision chain.

    Usage::

        telemetry = RiskTelemetry()
        trace = telemetry.start_trace()
        telemetry.add_event(trace, TraceSpan.CAPITAL_STATE, data={...})
        telemetry.add_event(trace, TraceSpan.STRESS_RESULT, data={...})
        telemetry.complete_trace(trace, action="INCREASE", outcome="EXECUTED")
    """

    def __init__(self, max_traces: int = 10000):
        self._traces: List[RiskDecisionTrace] = []
        self._max_traces = max_traces

    def start_trace(self) -> RiskDecisionTrace:
        """Start a new risk decision trace."""
        trace = RiskDecisionTrace(
            trace_id=str(uuid.uuid4())[:12],
            start_time=time.time(),
        )
        return trace

    def add_event(
        self,
        trace: RiskDecisionTrace,
        span: TraceSpan,
        data: Dict[str, Any],
        parent_span: Optional[TraceSpan] = None,
    ) -> TraceEvent:
        """Add an event to the trace.

        Args:
            trace: the trace to add to
            span: the span type
            data: event data
            parent_span: optional parent span
        """
        event = TraceEvent(
            span=span,
            trace_id=trace.trace_id,
            timestamp=time.time(),
            data=data,
            parent_span=parent_span,
        )
        trace.events.append(event)
        return event

    def complete_trace(
        self,
        trace: RiskDecisionTrace,
        action: str = "",
        outcome: str = "",
    ) -> RiskDecisionTrace:
        """Complete and store a trace.

        Args:
            trace: the trace to complete
            action: what action was taken
            outcome: what was the outcome
        """
        trace.end_time = time.time()
        trace.action_taken = action
        trace.outcome = outcome

        # extract survival scores from events
        for event in trace.events:
            if event.span == TraceSpan.SURVIVAL_SCORE:
                score = event.data.get("score", 100.0)
                if "pre" in event.data.get("phase", ""):
                    trace.pre_action_survival = score
                elif "post" in event.data.get("phase", ""):
                    trace.post_action_survival = score
                elif "stress" in event.data.get("phase", ""):
                    trace.stress_survival = score

        # decision summary
        trace.decision_summary = (
            f"{action}: survival {trace.pre_action_survival:.0f} → "
            f"{trace.post_action_survival:.0f} "
            f"(stress: {trace.stress_survival:.0f})"
        )

        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]

        return trace

    def get_trace(self, trace_id: str) -> Optional[RiskDecisionTrace]:
        """Get a specific trace by ID."""
        for t in self._traces:
            if t.trace_id == trace_id:
                return t
        return None

    def get_recent_traces(self, limit: int = 50) -> List[RiskDecisionTrace]:
        """Get recent traces."""
        return self._traces[-limit:]

    def get_action_explain(self, trace_id: str) -> Dict[str, Any]:
        """Get human-readable explanation of a decision trace.

        Explains: "Why was this action taken?"
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return {"error": "trace not found"}

        explanation = {
            "trace_id": trace.trace_id,
            "action": trace.action_taken,
            "outcome": trace.outcome,
            "summary": trace.decision_summary,
            "chain": [],
        }

        for event in trace.events:
            explanation["chain"].append({
                "step": event.span.name,
                "data": event.data,
            })

        return explanation

    def clear(self) -> None:
        """Clear all traces."""
        self._traces.clear()

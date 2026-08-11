"""
Control Plane Telemetry — End-to-end trace tracking for autonomous decisions.

Provides complete trace from research through execution with all
governance context for answerability: "Why was this trade executed?"
"""

from __future__ import annotations

import uuid
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Telemetry:
    """
    Unified telemetry for autonomous decision traces.

    Every autonomous decision creates a trace that spans:
        research → alpha → strategy → portfolio → risk →
        execution → fill → P&L
    with policy, approval, autonomy, and audit context.
    """

    def __init__(self):
        self._traces: dict[str, dict] = {}
        self._active_traces = 0

    def start_trace(
        self,
        trace_id: str = "",
        research_id: str = "",
        alpha_id: str = "",
        strategy_id: str = "",
    ) -> str:
        """Start a new telemetry trace."""
        tid = trace_id or str(uuid.uuid4())
        self._traces[tid] = {
            "trace_id": tid,
            "started_at": time.time(),
            "research_id": research_id,
            "alpha_id": alpha_id,
            "strategy_id": strategy_id,
            "portfolio_id": "",
            "position_id": "",
            "risk_decision_id": "",
            "execution_plan_id": "",
            "order_id": "",
            "execution_id": "",
            "fill_id": "",
            "policy_id": "",
            "policy_version": "",
            "autonomy_level": 0,
            "approval_id": "",
            "decision_id": "",
            "incident_id": "",
            "events": [],
        }
        self._active_traces += 1
        return tid

    def update(self, trace_id: str, **kwargs) -> bool:
        """Update a trace with additional context."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.update(kwargs)
            return True
        return False

    def add_event(self, trace_id: str, event: str, details: Optional[dict] = None):
        """Add an event to a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace["events"].append({
                "event": event,
                "timestamp": time.time(),
                "details": details or {},
            })

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self._traces.get(trace_id)

    def export_trace(self, trace_id: str) -> Optional[dict]:
        """Export a complete trace for audit/analysis."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        return {
            "trace_id": trace["trace_id"],
            "duration_seconds": time.time() - trace["started_at"],
            "pipeline": {
                "research_id": trace["research_id"],
                "alpha_id": trace["alpha_id"],
                "strategy_id": trace["strategy_id"],
                "portfolio_id": trace["portfolio_id"],
                "risk_decision_id": trace["risk_decision_id"],
                "execution_plan_id": trace["execution_plan_id"],
                "order_id": trace["order_id"],
                "execution_id": trace["execution_id"],
                "fill_id": trace["fill_id"],
            },
            "governance": {
                "policy_id": trace["policy_id"],
                "policy_version": trace["policy_version"],
                "autonomy_level": trace["autonomy_level"],
                "approval_id": trace["approval_id"],
                "decision_id": trace["decision_id"],
                "incident_id": trace["incident_id"],
            },
            "event_count": len(trace["events"]),
        }

    def stats(self) -> dict:
        return {
            "total_traces": len(self._traces),
            "active_traces": self._active_traces,
        }

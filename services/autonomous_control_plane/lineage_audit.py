"""
Lineage Audit — End-to-end lineage audit trail.

Connects the complete pipeline: Market Data → Hypothesis → Factor →
Alpha → Strategy → Portfolio → Risk Decision → Execution Plan →
Order → Fill → P&L, with all policy/approval/autonomy context.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LineageAudit:
    """
    End-to-end lineage audit for autonomous decisions.

    Every trade can be traced back through the full pipeline to its
    originating research decision, with all intermediate context.
    """

    def __init__(self):
        self._traces: dict[str, dict] = {}

    def start_trace(
        self,
        trace_id: str,
        research_id: str = "",
        alpha_id: str = "",
        strategy_id: str = "",
    ) -> dict:
        """Start a new trace with the initial research context."""
        trace = {
            "trace_id": trace_id,
            "research_id": research_id,
            "alpha_id": alpha_id,
            "strategy_id": strategy_id,
            "portfolio_id": "",
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
        self._traces[trace_id] = trace
        return trace

    def update_trace(self, trace_id: str, **kwargs) -> bool:
        """Update a trace with additional context."""
        trace = self._traces.get(trace_id)
        if not trace:
            return False
        trace.update({k: v for k, v in kwargs.items() if v})
        return True

    def add_event(self, trace_id: str, event: str, details: Optional[dict] = None):
        """Add an event to a trace."""
        import time
        trace = self._traces.get(trace_id)
        if trace:
            trace["events"].append({
                "event": event,
                "timestamp": time.time(),
                "details": details or {},
            })

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self._traces.get(trace_id)

    def reconstruct_pipeline(self, trace_id: str) -> dict:
        """Reconstruct the full pipeline from a single trace."""
        trace = self.get_trace(trace_id)
        if not trace:
            return {"error": "trace_not_found"}

        return {
            "trace_id": trace_id,
            "pipeline": [
                ("Market Data", True),
                ("Research", bool(trace.get("research_id"))),
                ("Alpha", bool(trace.get("alpha_id"))),
                ("Strategy", bool(trace.get("strategy_id"))),
                ("Portfolio", bool(trace.get("portfolio_id"))),
                ("Risk Decision", bool(trace.get("risk_decision_id"))),
                ("Execution Plan", bool(trace.get("execution_plan_id"))),
                ("Order", bool(trace.get("order_id"))),
                ("Execution", bool(trace.get("execution_id"))),
                ("Fill", bool(trace.get("fill_id"))),
            ],
            "governance": {
                "policy_id": trace.get("policy_id"),
                "policy_version": trace.get("policy_version"),
                "autonomy_level": trace.get("autonomy_level"),
                "approval_id": trace.get("approval_id"),
            },
            "events": len(trace.get("events", [])),
        }

    def stats(self) -> dict:
        return {
            "active_traces": len(self._traces),
            "complete_traces": sum(
                1 for t in self._traces.values() if t.get("fill_id")
            ),
        }

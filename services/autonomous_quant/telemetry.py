"""Autonomous Quant Telemetry — Complete tracing of research cycles.

Traces the full autonomous research trace:
    Market Event → Opportunity → Hypothesis → Experiment →
    Factor → Alpha → Strategy → Backtest → Validation → Candidate
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutonomyTelemetry:
    """Traces autonomous research cycles end-to-end."""

    def __init__(self) -> None:
        self._traces: List[Dict[str, Any]] = []

    async def start_trace(
        self,
        research_cycle_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        trace_id = f"trace_{research_cycle_id}"
        self._traces.append({
            "trace_id": trace_id,
            "research_cycle_id": research_cycle_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "spans": [],
            "context": context or {},
        })
        return trace_id

    async def add_span(
        self,
        trace_id: str,
        span_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        for trace in self._traces:
            if trace["trace_id"] == trace_id:
                trace["spans"].append({
                    "span_name": span_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": metadata or {},
                })
                break

    async def end_trace(self, trace_id: str, status: str = "completed") -> None:
        for trace in self._traces:
            if trace["trace_id"] == trace_id:
                trace["ended_at"] = datetime.now(timezone.utc).isoformat()
                trace["status"] = status
                break

    def get_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._traces[-limit:]

    def trace_count(self) -> int:
        return len(self._traces)

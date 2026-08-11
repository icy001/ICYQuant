"""
Capital Telemetry — End-to-end tracing for capital decisions.

Trace path:
    capital_pool_id → account_id → strategy_id → portfolio_id
    → allocation_decision_id → risk_decision_id → execution_plan_id
    → capital_deployed → realized_pnl → capital_efficiency

Also associates: policy_version, autonomy_level, approval_id, model_version.

Provides full capital lineage: Capital → Strategy → Risk → Execution → P&L.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CapitalSpan:
    """A span in the capital decision trace."""

    span_id: str = field(default_factory=lambda: f"SPAN-{uuid.uuid4().hex[:8]}")
    trace_id: str = ""
    parent_span_id: str = ""

    operation: str = ""                 # e.g. "allocate", "reserve", "deploy"
    start_time: str = ""
    end_time: str = ""

    # Context
    capital_pool_id: str = ""
    account_id: str = ""
    strategy_id: str = ""
    portfolio_id: str = ""
    allocation_decision_id: str = ""
    risk_decision_id: str = ""
    execution_plan_id: str = ""

    # Policy/autonomy context from Commit 18
    policy_version: str = ""
    autonomy_level: int = 0
    approval_id: str = ""
    model_version: str = ""

    # Values
    capital_amount: float = 0.0
    realized_pnl: float = 0.0
    capital_efficiency: float = 0.0

    # Status
    status: str = "OK"
    error: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "capital_pool_id": self.capital_pool_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "allocation_decision_id": self.allocation_decision_id,
            "risk_decision_id": self.risk_decision_id,
            "execution_plan_id": self.execution_plan_id,
            "policy_version": self.policy_version,
            "autonomy_level": self.autonomy_level,
            "capital_amount": self.capital_amount,
            "realized_pnl": self.realized_pnl,
            "capital_efficiency": self.capital_efficiency,
            "status": self.status,
        }


@dataclass
class CapitalTrace:
    """A complete trace of a capital decision lifecycle."""

    trace_id: str = field(default_factory=lambda: f"TRACE-{uuid.uuid4().hex[:8]}")
    root_operation: str = ""
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str = ""
    spans: List[CapitalSpan] = field(default_factory=list)
    status: str = "RUNNING"

    def add_span(self, span: CapitalSpan) -> None:
        span.trace_id = self.trace_id
        self.spans.append(span)

    def span_count(self) -> int:
        return len(self.spans)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_operation": self.root_operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }

    def complete(self) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = "COMPLETED"

    def fail(self, error: str) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = "FAILED"
        if self.spans:
            self.spans[-1].error = error
            self.spans[-1].status = "ERROR"


class CapitalTelemetry:
    """Manages capital decision tracing and lineage."""

    def __init__(self, max_traces: int = 10000):
        self._traces: Dict[str, CapitalTrace] = {}
        self._max_traces = max_traces

    def start_trace(self, operation: str) -> CapitalTrace:
        trace = CapitalTrace(root_operation=operation)
        self._traces[trace.trace_id] = trace
        self._evict_if_needed()
        return trace

    def add_span(self, trace_id: str, span: CapitalSpan) -> bool:
        trace = self._traces.get(trace_id)
        if trace:
            trace.add_span(span)
            return True
        return False

    def get_trace(self, trace_id: str) -> Optional[CapitalTrace]:
        return self._traces.get(trace_id)

    def get_capital_lineage(self, strategy_id: str) -> List[CapitalSpan]:
        """Find all spans related to a strategy's capital."""
        spans = []
        for trace in self._traces.values():
            for span in trace.spans:
                if span.strategy_id == strategy_id:
                    spans.append(span)
        return spans

    def get_pool_lineage(self, pool_id: str) -> List[CapitalSpan]:
        """Find all spans related to a capital pool."""
        spans = []
        for trace in self._traces.values():
            for span in trace.spans:
                if span.capital_pool_id == pool_id:
                    spans.append(span)
        return spans

    def active_traces(self) -> List[CapitalTrace]:
        return [t for t in self._traces.values() if t.status == "RUNNING"]

    def recent_traces(self, n: int = 20) -> List[CapitalTrace]:
        traces = sorted(self._traces.values(), key=lambda t: t.start_time, reverse=True)
        return traces[:n]

    def _evict_if_needed(self) -> None:
        if len(self._traces) > self._max_traces:
            sorted_traces = sorted(self._traces.items(), key=lambda x: x[1].start_time)
            to_remove = len(self._traces) - self._max_traces
            for trace_id, _ in sorted_traces[:to_remove]:
                del self._traces[trace_id]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_traces": len(self._traces),
            "active_traces": len(self.active_traces()),
            "total_spans": sum(t.span_count() for t in self._traces.values()),
        }

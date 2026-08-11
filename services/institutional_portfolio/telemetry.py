"""
Portfolio Telemetry — Full Capital Lineage Tracing

Tracing capital/signal lineage through the portfolio pipeline:

    strategy_signal → signal_aggregation → signal_netting →
    position_aggregation → position_netting → portfolio_decision →
    capital_decision → risk_decision → rebalance_decision →
    execution_plan → orders → fills

Any final order can be traced back to the original strategies,
signal netting, and portfolio decisions.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    strategy_id: Optional[str] = None
    asset: Optional[str] = None
    amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PortfolioTelemetry:
    """
    Capital lineage tracing for the full portfolio pipeline.

    Every trade can be traced: which strategies contributed signals,
    how they were netted, what portfolio decision resulted, and
    how capital was routed.
    """

    def __init__(
        self,
        telemetry_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.telemetry_id = telemetry_id or f"ptel-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._trace_id: Optional[str] = None
        self._spans: List[TraceSpan] = []
        self._span_stack: List[str] = []

    def start_trace(self) -> str:
        self._trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        self._spans.clear()
        self._span_stack.clear()
        return self._trace_id

    def start_span(self, operation: str, **kwargs) -> str:
        span_id = f"span-{uuid.uuid4().hex[:8]}"
        parent = self._span_stack[-1] if self._span_stack else None
        span = TraceSpan(
            span_id=span_id,
            parent_span_id=parent,
            operation=operation,
            **kwargs,
        )
        self._spans.append(span)
        self._span_stack.append(span_id)
        return span_id

    def end_span(self) -> None:
        if self._span_stack:
            self._span_stack.pop()

    def get_trace(self) -> Dict[str, Any]:
        """Full trace tree for analysis."""
        return {
            "trace_id": self._trace_id,
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent": s.parent_span_id,
                    "operation": s.operation,
                    "strategy_id": s.strategy_id,
                    "asset": s.asset,
                    "amount": s.amount,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self._spans
            ],
        }

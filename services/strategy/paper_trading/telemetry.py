"""
Paper Trading Telemetry
========================
Distributed tracing for the paper trading pipeline.

Spans:
    Paper Trading Timeline   — Order submission to execution
    Execution Timeline       — Simulated execution path
    Evaluation Timeline      — Performance evaluation
    Promotion Timeline       — Strategy promotion workflow
    Audit Trail              — Full end-to-end trace
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PTSpanKind(str, Enum):
    """Paper trading span kinds."""
    ORDER = "order"
    EXECUTION = "execution"
    MATCHING = "matching"
    SLIPPAGE = "slippage"
    COMMISSION = "commission"
    PORTFOLIO = "portfolio"
    EVALUATION = "evaluation"
    PROMOTION = "promotion"
    AUDIT = "audit"


class PTSpanStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class PTSpan:
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    kind: PTSpanKind
    name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: PTSpanStatus = PTSpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if not self.ended_at:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds() * 1000.0

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })


@dataclass
class PTTrace:
    trace_id: str
    session_id: str
    strategy_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    spans: List[PTSpan] = field(default_factory=list)
    total_orders: int = 0
    total_trades: int = 0
    status: PTSpanStatus = PTSpanStatus.OK

    @property
    def total_duration_ms(self) -> float:
        if not self.ended_at:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds() * 1000.0

    @property
    def span_count(self) -> int:
        return len(self.spans)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "total_orders": self.total_orders,
            "total_trades": self.total_trades,
            "status": self.status.value,
            "span_count": self.span_count,
            "spans": [
                {
                    "span_id": s.span_id,
                    "kind": s.kind.value,
                    "name": s.name,
                    "status": s.status.value,
                    "duration_ms": round(s.duration_ms, 3),
                    "attributes": s.attributes,
                }
                for s in self.spans
            ],
        }


class PaperTradingTelemetry:
    """Distributed telemetry for the paper trading pipeline."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._traces: Dict[str, PTTrace] = {}
        self._completed: List[PTTrace] = []
        self._max_completed = 100

    def start_trace(self, session_id: str, strategy_id: str) -> PTTrace:
        trace = PTTrace(
            trace_id=f"pttrace_{uuid4().hex[:12]}",
            session_id=session_id,
            strategy_id=strategy_id,
            started_at=datetime.now(timezone.utc),
        )
        self._traces[trace.trace_id] = trace
        return trace

    def end_trace(self, trace_id: str, status: PTSpanStatus = PTSpanStatus.OK) -> Optional[PTTrace]:
        trace = self._traces.pop(trace_id, None)
        if not trace:
            return None
        trace.ended_at = datetime.now(timezone.utc)
        trace.status = status
        self._completed.append(trace)
        if len(self._completed) > self._max_completed:
            self._completed = self._completed[-self._max_completed:]
        return trace

    def start_span(self, trace_id: str, kind: PTSpanKind, name: str,
                   parent_span_id: Optional[str] = None,
                   attributes: Optional[Dict[str, Any]] = None) -> PTSpan:
        span = PTSpan(
            span_id=f"ptspan_{uuid4().hex[:8]}",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name,
            started_at=datetime.now(timezone.utc),
            attributes=attributes or {},
        )
        trace = self._traces.get(trace_id)
        if trace:
            trace.spans.append(span)
        return span

    def end_span(self, span: PTSpan, status: PTSpanStatus = PTSpanStatus.OK,
                 error_message: Optional[str] = None,
                 attributes: Optional[Dict[str, Any]] = None) -> None:
        span.ended_at = datetime.now(timezone.utc)
        span.status = status
        span.error_message = error_message
        if attributes:
            span.attributes.update(attributes)

    def trace_order(self, trace_id: str, parent_span_id: str,
                    order_id: str, instrument: str, side: str,
                    quantity: float) -> PTSpan:
        return self.start_span(trace_id, PTSpanKind.ORDER, f"order:{order_id}",
                               parent_span_id, {"order_id": order_id,
                                                "instrument": instrument,
                                                "side": side, "quantity": quantity})

    def trace_execution(self, trace_id: str, parent_span_id: str,
                        order_id: str) -> PTSpan:
        return self.start_span(trace_id, PTSpanKind.EXECUTION, f"exec:{order_id}",
                               parent_span_id, {"order_id": order_id})

    def trace_slippage(self, trace_id: str, parent_span_id: str,
                       order_id: str, model: str) -> PTSpan:
        return self.start_span(trace_id, PTSpanKind.SLIPPAGE, f"slip:{order_id}",
                               parent_span_id, {"order_id": order_id, "model": model})

    def trace_evaluation(self, trace_id: str, parent_span_id: str,
                         strategy_id: str) -> PTSpan:
        return self.start_span(trace_id, PTSpanKind.EVALUATION,
                               f"eval:{strategy_id}", parent_span_id,
                               {"strategy_id": strategy_id})

    def trace_promotion(self, trace_id: str, parent_span_id: str,
                        strategy_id: str, stage: str) -> PTSpan:
        return self.start_span(trace_id, PTSpanKind.PROMOTION,
                               f"promote:{strategy_id}", parent_span_id,
                               {"strategy_id": strategy_id, "stage": stage})

    def get_trace(self, trace_id: str) -> Optional[PTTrace]:
        return self._traces.get(trace_id)

    def recent_traces(self, limit: int = 20) -> List[PTTrace]:
        return self._completed[-limit:]

    def reset(self) -> None:
        self._traces.clear()
        self._completed.clear()

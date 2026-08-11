"""Allocation Result — execution result of an allocation decision.

Captures: what was requested vs what was executed,
including realized costs, slippage, and feedback data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ResultStatus(str, Enum):
    """Execution result status."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutionMetrics:
    """Metrics from the actual execution."""
    fill_quantity: float = 0.0
    fill_price: float = 0.0
    expected_price: float = 0.0
    realized_cost: float = 0.0
    realized_impact: float = 0.0
    realized_slippage: float = 0.0
    commission: float = 0.0
    spread_cost: float = 0.0
    execution_time_ms: float = 0.0
    venue: str = ""

    @property
    def price_deviation_bps(self) -> float:
        if self.expected_price <= 0:
            return 0.0
        return (self.fill_price / self.expected_price - 1) * 10000

    @property
    def total_cost_bps(self) -> float:
        """Total execution cost in basis points."""
        if self.fill_quantity <= 0 or self.fill_price <= 0:
            return 0.0
        notional = self.fill_quantity * self.fill_price
        total_cost = (self.realized_cost + self.commission +
                      self.spread_cost + self.realized_slippage)
        return (total_cost / notional) * 10000 if notional > 0 else 0.0


@dataclass
class PredictionError:
    """Difference between predicted and realized values."""
    metric: str = ""
    predicted: float = 0.0
    realized: float = 0.0

    @property
    def error(self) -> float:
        return self.realized - self.predicted

    @property
    def error_ratio(self) -> float:
        if self.predicted == 0:
            return 0.0
        return self.error / abs(self.predicted)

    @property
    def absolute_error(self) -> float:
        return abs(self.error)


@dataclass
class AllocationResult:
    """Complete result of executing an allocation decision."""

    strategy_id: str
    decision_id: str = ""
    status: ResultStatus = ResultStatus.SUCCESS

    # Requested vs Executed
    requested_delta: float = 0.0
    executed_delta: float = 0.0
    requested_capital: float = 0.0
    executed_capital: float = 0.0

    # Execution metrics
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    # Prediction errors
    prediction_errors: List[PredictionError] = field(default_factory=list)

    # Feedback
    alpha_revision: float = 0.0
    risk_revision: float = 0.0
    capacity_revision: float = 0.0
    impact_revision: float = 0.0

    # Meta
    result_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    execution_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.result_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.result_id = f"res-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"

    @property
    def fill_rate(self) -> float:
        if self.requested_delta == 0:
            return 1.0
        return self.executed_delta / self.requested_delta

    @property
    def is_complete(self) -> bool:
        return self.status == ResultStatus.SUCCESS and abs(self.fill_rate - 1.0) < 1e-6

    def add_prediction_error(self, metric: str, predicted: float,
                             realized: float) -> PredictionError:
        """Record a prediction vs realized error."""
        pe = PredictionError(metric=metric, predicted=predicted, realized=realized)
        self.prediction_errors.append(pe)
        return pe

    def get_error(self, metric: str) -> Optional[PredictionError]:
        """Get a specific prediction error by metric name."""
        for pe in self.prediction_errors:
            if pe.metric == metric:
                return pe
        return None

    def summarize(self) -> str:
        """Generate a human-readable result summary."""
        lines = [
            f"AllocationResult[{self.result_id}] {self.status.value}",
            f"  Strategy: {self.strategy_id}",
            f"  Delta: requested={self.requested_delta:+,.0f}, "
            f"executed={self.executed_delta:+,.0f} ({self.fill_rate:.1%})",
            f"  Capital: {self.requested_capital:,.0f} → {self.executed_capital:,.0f}",
        ]
        if self.execution.fill_quantity > 0:
            lines.append(
                f"  Price: expected={self.execution.expected_price:.4f}, "
                f"fill={self.execution.fill_price:.4f} "
                f"(dev={self.execution.price_deviation_bps:.1f}bps)"
            )
            lines.append(f"  Cost: {self.execution.total_cost_bps:.1f}bps total")
        if self.prediction_errors:
            lines.append("  Prediction Errors:")
            for pe in self.prediction_errors:
                lines.append(
                    f"    {pe.metric}: predicted={pe.predicted:.4f}, "
                    f"realized={pe.realized:.4f} (err={pe.error:+.4f})"
                )
        return "\n".join(lines)

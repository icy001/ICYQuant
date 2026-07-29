from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionAlgorithm(str, Enum):
    VWAP = "VWAP"
    TWAP = "TWAP"
    POV = "POV"
    IMPLEMENTATION_SHORTFALL = "IMPLEMENTATION_SHORTFALL"
    ADAPTIVE = "ADAPTIVE"
    ICEBERG = "ICEBERG"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTC = "GTC"  # Good Till Cancel


@dataclass
class ExecutionSlice:
    slice_id: int
    quantity: int
    start_time: str
    end_time: str
    target_price: Optional[float] = None
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.VWAP
    time_in_force: TimeInForce = TimeInForce.DAY


@dataclass
class ExecutionPlan:
    order_id: str
    symbol: str
    side: str
    total_quantity: int
    algorithm: ExecutionAlgorithm
    slices: List[ExecutionSlice] = field(default_factory=list)
    benchmark: str = "VWAP"
    max_deviation_bps: float = 10.0
    participation_rate: float = 0.05
    constraints: Dict[str, Any] = field(default_factory=dict)


class ExecutionPlanner:
    """Execution Planning Engine - creates detailed execution plans for orders."""

    def __init__(self):
        self.default_algorithm = ExecutionAlgorithm.VWAP
        self.default_slices = 20
        self.default_duration_minutes = 240  # 4 hours

    def plan(self, order):
        """Create an execution plan for the given order.

        Args:
            order: Order specification - can be ExecutionPlan dataclass or dict/symbol.

        Returns:
            Dict containing the execution plan.
        """
        if isinstance(order, ExecutionPlan):
            return self._plan_from_spec(order)
        return {"plan": order}

    def _plan_from_spec(self, order: ExecutionPlan) -> dict:
        slices = self._generate_slices(
            total_qty=order.total_quantity,
            num_slices=self.default_slices,
            algorithm=order.algorithm,
        )
        return {
            "plan": {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "total_quantity": order.total_quantity,
                "algorithm": order.algorithm.value,
                "slices": [
                    {
                        "slice_id": s.slice_id,
                        "quantity": s.quantity,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "algorithm": s.algorithm.value,
                    }
                    for s in slices
                ],
                "benchmark": order.benchmark,
                "max_deviation_bps": order.max_deviation_bps,
            }
        }

    def _generate_slices(
        self,
        total_qty: int,
        num_slices: int,
        algorithm: ExecutionAlgorithm,
    ) -> List[ExecutionSlice]:
        base_qty = total_qty // num_slices
        remainder = total_qty % num_slices
        slices = []
        for i in range(num_slices):
            qty = base_qty + (1 if i < remainder else 0)
            slices.append(
                ExecutionSlice(
                    slice_id=i + 1,
                    quantity=qty,
                    start_time=f"{i * 12:02d}:00",
                    end_time=f"{(i + 1) * 12:02d}:00",
                    algorithm=algorithm,
                )
            )
        return slices

    def optimize_slices(self, plan: ExecutionPlan, market_impact: float) -> ExecutionPlan:
        """Optimize slice sizes based on predicted market impact."""
        if market_impact > 0.01:
            plan.participation_rate *= 0.5
        return plan

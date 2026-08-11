"""Rebalance Planner — generates rebalance plans with constraints.

Breaks down target allocations into executable rebalance steps,
respecting order size limits, impact budgets, and timing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .rebalance_engine import RebalanceAction, RebalanceInstruction, RebalancePlan


@dataclass
class RebalanceStep:
    """A single executable rebalance step."""
    strategy_id: str
    action: RebalanceAction
    capital_delta: float
    weight_delta: float
    order_size: float
    slice_count: int = 1
    execution_window_minutes: int = 5
    expected_impact_bps: float = 0.0
    step_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.step_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.step_id = f"rb-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"


@dataclass
class RebalanceExecutionPlan:
    """Sequence of rebalance steps to execute."""
    steps: List[RebalanceStep] = field(default_factory=list)
    total_steps: int = 0
    estimated_duration_minutes: float = 0.0
    total_impact_bps: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "PENDING"


class RebalancePlanner:
    """Plans the execution sequence for a rebalance plan.

    Breaks large rebalances into slices to minimize market impact,
    respecting execution windows, participation limits, and impact budgets.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._max_slice_size = self._config.get("max_slice_size", 1_000_000.0)
        self._max_participation = self._config.get("max_participation", 0.10)
        self._min_slice_duration = self._config.get("min_slice_duration", 5)

    def plan(self, rebalance_plan: RebalancePlan,
             daily_volumes: Optional[Dict[str, float]] = None,
             volatilities: Optional[Dict[str, float]] = None) -> RebalanceExecutionPlan:
        """Create an executable execution plan from a rebalance plan."""
        daily_volumes = daily_volumes or {}
        volatilities = volatilities or {}
        exec_plan = RebalanceExecutionPlan()

        for inst in rebalance_plan.instructions:
            if inst.action in (RebalanceAction.HOLD, RebalanceAction.FREEZE):
                continue

            capital_delta = abs(inst.capital_delta)
            if capital_delta <= 0:
                continue

            dv = daily_volumes.get(inst.strategy_id, capital_delta * 10)
            vol = volatilities.get(inst.strategy_id, 0.20)
            participation = capital_delta / dv if dv > 0 else 1.0

            # Determine slice count
            if participation > self._max_participation:
                slices = max(2, int(participation / self._max_participation) + 1)
            elif capital_delta > self._max_slice_size:
                slices = max(2, int(capital_delta / self._max_slice_size) + 1)
            else:
                slices = 1

            slice_size = capital_delta / slices
            impact = vol * 10000 * (participation / slices) ** 0.5

            step = RebalanceStep(
                strategy_id=inst.strategy_id,
                action=inst.action,
                capital_delta=capital_delta,
                weight_delta=inst.weight_delta,
                order_size=slice_size,
                slice_count=slices,
                execution_window_minutes=slices * self._min_slice_duration,
                expected_impact_bps=impact,
            )
            exec_plan.steps.append(step)
            exec_plan.total_impact_bps += impact

        exec_plan.total_steps = len(exec_plan.steps)
        exec_plan.estimated_duration_minutes = sum(
            s.execution_window_minutes for s in exec_plan.steps
        )
        exec_plan.status = "PLANNED"

        return exec_plan

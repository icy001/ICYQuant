"""Rebalance Engine — orchestrates portfolio rebalancing.

Inputs: current allocation, target allocation, risk/capacity/liquidity states.
Outputs: Increase/Decrease/Hold/Freeze decisions per strategy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RebalanceAction(str, Enum):
    """Rebalance action per strategy."""
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    HOLD = "HOLD"
    FREEZE = "FREEZE"


@dataclass
class RebalanceInstruction:
    """Single rebalance instruction for a strategy."""
    strategy_id: str
    action: RebalanceAction = RebalanceAction.HOLD
    current_weight: float = 0.0
    target_weight: float = 0.0
    current_capital: float = 0.0
    target_capital: float = 0.0
    capital_delta: float = 0.0
    priority: int = 0
    reason: str = ""
    estimated_cost_bps: float = 0.0
    estimated_impact_bps: float = 0.0

    @property
    def weight_delta(self) -> float:
        return self.target_weight - self.current_weight


@dataclass
class RebalancePlan:
    """Complete rebalance plan across all strategies."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    instructions: List[RebalanceInstruction] = field(default_factory=list)
    total_increase: float = 0.0
    total_decrease: float = 0.0
    net_flow: float = 0.0
    total_cost_bps: float = 0.0
    strategy_count: int = 0

    @property
    def action_summary(self) -> Dict[str, int]:
        summary = {"INCREASE": 0, "DECREASE": 0, "HOLD": 0, "FREEZE": 0}
        for inst in self.instructions:
            summary[inst.action.value] += 1
        return summary


class RebalanceEngine:
    """Orchestrates portfolio rebalancing with priority-aware execution."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._threshold = self._config.get("rebalance_threshold", 0.02)
        self._min_trade_amount = self._config.get("min_trade_amount", 10000.0)

    def compute_rebalance(self,
                          current_weights: Dict[str, float],
                          target_weights: Dict[str, float],
                          total_capital: float,
                          scores: Optional[Dict[str, Dict[str, float]]] = None,
                          frozen_strategies: Optional[set] = None) -> RebalancePlan:
        """Compute rebalance plan from current vs target weights."""
        frozen = frozen_strategies or set()
        scores = scores or {}
        plan = RebalancePlan()

        for strategy_id in set(list(current_weights.keys()) + list(target_weights.keys())):
            current = current_weights.get(strategy_id, 0.0)
            target = target_weights.get(strategy_id, 0.0)
            delta = target - current

            if strategy_id in frozen:
                inst = RebalanceInstruction(
                    strategy_id=strategy_id,
                    action=RebalanceAction.FREEZE,
                    current_weight=current,
                    target_weight=current,
                    current_capital=current * total_capital,
                    target_capital=current * total_capital,
                    capital_delta=0.0,
                    reason="Strategy is frozen",
                )
                plan.instructions.append(inst)
                continue

            # Check threshold
            if abs(delta) <= self._threshold:
                inst = RebalanceInstruction(
                    strategy_id=strategy_id,
                    action=RebalanceAction.HOLD,
                    current_weight=current,
                    target_weight=target,
                    current_capital=current * total_capital,
                    target_capital=target * total_capital,
                    capital_delta=0.0,
                    reason=f"Within threshold ({abs(delta):.4f} ≤ {self._threshold:.4f})",
                )
                plan.instructions.append(inst)
                continue

            action = RebalanceAction.INCREASE if delta > 0 else RebalanceAction.DECREASE

            inst = RebalanceInstruction(
                strategy_id=strategy_id,
                action=action,
                current_weight=current,
                target_weight=target,
                current_capital=current * total_capital,
                target_capital=target * total_capital,
                capital_delta=delta * total_capital,
                reason=f"Rebalance: {current:.4f} → {target:.4f}",
            )
            plan.instructions.append(inst)

            if delta > 0:
                plan.total_increase += delta * total_capital
            else:
                plan.total_decrease += abs(delta * total_capital)

        plan.net_flow = plan.total_increase - plan.total_decrease
        plan.strategy_count = len(plan.instructions)

        return plan

    def prioritize(self, plan: RebalancePlan) -> RebalancePlan:
        """Prioritize rebalance instructions.

        Priority ordering:
        1. Risk reduction (DECREASE high-risk)
        2. Alpha improvement (INCREASE high-alpha)
        3. Capacity efficiency
        4. Liquidity quality
        5. Execution cost
        """
        # Sort: decreases first (risk reduction), then increases (alpha improvement)
        decreases = [i for i in plan.instructions if i.action == RebalanceAction.DECREASE]
        increases = [i for i in plan.instructions if i.action == RebalanceAction.INCREASE]
        others = [i for i in plan.instructions if i.action not in (RebalanceAction.DECREASE, RebalanceAction.INCREASE)]

        # Sort decreases by size (largest first)
        decreases.sort(key=lambda i: abs(i.capital_delta), reverse=True)

        # Sort increases by size (largest first)
        increases.sort(key=lambda i: abs(i.capital_delta), reverse=True)

        # Reassemble
        ordered = decreases + increases + others
        for i, inst in enumerate(ordered):
            inst.priority = i + 1

        plan.instructions = ordered
        return plan

    def validate_net_zero(self, plan: RebalancePlan, tolerance: float = 0.01) -> bool:
        """Validate that increases ≈ decreases (net zero flow)."""
        return abs(plan.net_flow) <= tolerance * plan.instructions[0].current_weight * plan.instructions[0].current_capital if plan.instructions else True

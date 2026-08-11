"""
Capacity Efficiency — Strategy Capacity Utilization vs Ideal

Measures how close each strategy is to its optimal capacity.
Overshooting capacity = diminishing returns; undershooting = idle capacity.

    Capacity Efficiency = Optimal Allocation / Capacity
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapacityEfficiencyRecord:
    strategy_id: str
    current_allocation: float = 0.0
    optimal_capital: float = 0.0
    max_capacity: float = float("inf")
    efficiency_score: float = 1.0
    utilization: float = 0.0
    gap_to_optimal: float = 0.0
    action: str = "HOLD"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapacityEfficiency:
    """
    Evaluates capacity efficiency for each strategy.

    Efficiency = 1.0 at optimal; drops above optimal (diminishing returns)
    and below optimal (underutilized capacity).

    Generates recommended actions:
    - INCREASE: well below optimal, has capacity
    - HOLD: near optimal
    - REDUCE: above optimal, diminishing returns
    - AT_CAPACITY: at max capacity
    """

    def __init__(
        self,
        efficiency_id: Optional[str] = None,
        strategy_capacity=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.efficiency_id = efficiency_id or f"cape-{uuid.uuid4().hex[:12]}"
        self._strategy_capacity = strategy_capacity
        self.config = config or {}
        self._records: Dict[str, CapacityEfficiencyRecord] = {}
        self._optimal_band = self.config.get("optimal_band", 0.15)

    def evaluate(self, strategy_id: str) -> Optional[CapacityEfficiencyRecord]:
        """Evaluate capacity efficiency for a strategy."""
        if not self._strategy_capacity:
            return None

        profile = self._strategy_capacity.get(strategy_id)
        if not profile:
            return None

        current = profile.current_allocation
        optimal = profile.optimal_capital
        max_cap = profile.max_capacity

        # Efficiency score: 1.0 at optimal, decays as distance increases
        if optimal > 0:
            ratio = current / optimal
            if ratio <= 1.0:
                efficiency = ratio  # 0→1 as we approach optimal
            else:
                overage = (current - optimal) / (max_cap - optimal) if max_cap > optimal else 0
                efficiency = max(0.0, 1.0 - overage)
        else:
            efficiency = 0.0

        utilization = current / max_cap if max_cap > 0 else 1.0
        gap = optimal - current

        # Determine action
        if utilization >= 0.99:
            action = "AT_CAPACITY"
        elif current > optimal * (1 + self._optimal_band):
            action = "REDUCE"
        elif current < optimal * (1 - self._optimal_band):
            action = "INCREASE"
        else:
            action = "HOLD"

        record = CapacityEfficiencyRecord(
            strategy_id=strategy_id,
            current_allocation=current,
            optimal_capital=optimal,
            max_capacity=max_cap,
            efficiency_score=efficiency,
            utilization=utilization,
            gap_to_optimal=gap,
            action=action,
        )
        self._records[strategy_id] = record
        return record

    def get_recommendations(self) -> Dict[str, Dict[str, Any]]:
        """Get recommended capital actions for all strategies."""
        recs = {}
        for sid, r in self._records.items():
            recs[sid] = {
                "action": r.action,
                "current": r.current_allocation,
                "optimal": r.optimal_capital,
                "gap": r.gap_to_optimal,
                "efficiency": r.efficiency_score,
            }
        return recs

    def get_summary(self) -> Dict[str, Any]:
        return {
            "efficiency_id": self.efficiency_id,
            "recommendations": self.get_recommendations(),
        }

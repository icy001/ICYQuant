"""
Strategy Capacity — Optimal Capital Sizing per Strategy

Models the non-linear relationship between capital and return:
- Below optimal: returns scale linearly
- Above optimal: diminishing returns (market impact, slippage, alpha decay)
- Above max capacity: negative marginal returns

    Effective Capital ≤ Strategy Capacity
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapacityProfile:
    strategy_id: str
    optimal_capital: float
    max_capacity: float
    current_allocation: float = 0.0
    expected_return_at_optimal: float = 0.0
    decay_rate: float = 0.5   # How fast efficiency decays past optimal
    min_return_pct: float = 0.02

    @property
    def utilization(self) -> float:
        if self.max_capacity <= 0:
            return 1.0
        return min(1.0, self.current_allocation / self.max_capacity)

    def estimate_return(self, capital: float) -> float:
        """Estimate return for a given capital level."""
        if capital <= self.optimal_capital:
            return self.expected_return_at_optimal * (capital / self.optimal_capital) if self.optimal_capital > 0 else 0.0
        excess = capital - self.optimal_capital
        decay = self.expected_return_at_optimal * (
            (excess / self.max_capacity) ** self.decay_rate
        ) if self.max_capacity > 0 else 0.0
        return max(self.expected_return_at_optimal * self.min_return_pct,
                   self.expected_return_at_optimal + self.expected_return_at_optimal * 0.1 * (excess / max(1, self.max_capacity)) - decay)


class StrategyCapacity:
    """
    Manages strategy capacity profiles and computes marginal efficiency.

    Key insight: capital allocation is NOT linear. Each strategy has
    an optimal range and a max capacity. Beyond optimal, market impact,
    slippage, and alpha decay reduce efficiency.
    """

    def __init__(
        self,
        capacity_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.capacity_id = capacity_id or f"scap-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._profiles: Dict[str, CapacityProfile] = {}

    def register(
        self,
        strategy_id: str,
        optimal_capital: float,
        max_capacity: float,
        expected_return: float = 0.0,
    ) -> CapacityProfile:
        profile = CapacityProfile(
            strategy_id=strategy_id,
            optimal_capital=optimal_capital,
            max_capacity=max_capacity,
            expected_return_at_optimal=expected_return,
        )
        self._profiles[strategy_id] = profile
        return profile

    def get(self, strategy_id: str) -> Optional[CapacityProfile]:
        return self._profiles.get(strategy_id)

    def update_allocation(self, strategy_id: str, amount: float) -> None:
        profile = self._profiles.get(strategy_id)
        if profile:
            profile.current_allocation = amount

    def get_marginal_return(self, strategy_id: str, additional: float) -> float:
        """Estimate the marginal return of adding capital to a strategy."""
        profile = self._profiles.get(strategy_id)
        if not profile:
            return 0.0
        current_return = profile.estimate_return(profile.current_allocation)
        new_return = profile.estimate_return(profile.current_allocation + additional)
        return new_return - current_return

    def get_marginal_efficiency(self, strategy_id: str, additional: float) -> float:
        """Marginal return per unit of additional capital."""
        mr = self.get_marginal_return(strategy_id, additional)
        return mr / additional if additional > 0 else 0.0

    def get_all_profiles(self) -> Dict[str, CapacityProfile]:
        return dict(self._profiles)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "capacity_id": self.capacity_id,
            "strategies": {
                sid: {
                    "optimal": p.optimal_capital,
                    "max": p.max_capacity,
                    "current": p.current_allocation,
                    "utilization": p.utilization,
                    "expected_return": p.expected_return_at_optimal,
                }
                for sid, p in self._profiles.items()
            },
        }

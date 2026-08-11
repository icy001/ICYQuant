"""
Strategy Capacity — Maximum capital a strategy can deploy without destroying alpha.

Capacity = MIN(Alpha Capacity, Market Capacity, Liquidity Capacity,
               Execution Capacity, Risk Capacity, Operational Capacity)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyCapacityState(str, Enum):
    UNDER_CAPACITY = "under_capacity"
    OPTIMAL = "optimal"
    APPROACHING = "approaching"
    AT_CAPACITY = "at_capacity"
    OVER_CAPACITY = "over_capacity"


@dataclass
class CapacityComponent:
    """A single component of strategy capacity."""

    name: str = ""
    limit: float = float("inf")
    current: float = 0.0
    utilization: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "limit": self.limit, "current": self.current, "utilization": self.utilization}


@dataclass
class StrategyCapacity:
    """Capacity assessment for a single strategy."""

    capacity_id: str = field(default_factory=lambda: f"SC-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    strategy_name: str = ""

    # Capacity limits
    optimal_capital: float = 0.0
    max_capacity: float = float("inf")

    # Components: most restrictive wins
    alpha_capacity: float = float("inf")
    market_capacity: float = float("inf")
    liquidity_capacity: float = float("inf")
    execution_capacity: float = float("inf")
    risk_capacity: float = float("inf")
    operational_capacity: float = float("inf")

    # Current state
    current_capital: float = 0.0
    utilization: float = 0.0
    state: StrategyCapacityState = StrategyCapacityState.UNDER_CAPACITY

    # Performance metrics
    expected_return: float = 0.0
    realized_return: float = 0.0
    marginal_return: float = 0.0
    alpha_decay_rate: float = 0.0

    @property
    def effective_capacity(self) -> float:
        """Most restrictive capacity = MIN of all components."""
        return min(
            self.alpha_capacity,
            self.market_capacity,
            self.liquidity_capacity,
            self.execution_capacity,
            self.risk_capacity,
            self.operational_capacity,
        )

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.effective_capacity - self.current_capital)

    @property
    def binding_constraint(self) -> str:
        caps = {
            "alpha": self.alpha_capacity,
            "market": self.market_capacity,
            "liquidity": self.liquidity_capacity,
            "execution": self.execution_capacity,
            "risk": self.risk_capacity,
            "operational": self.operational_capacity,
        }
        return min(caps, key=caps.get) if caps else "unknown"

    def evaluate_state(self) -> StrategyCapacityState:
        if self.max_capacity == float("inf"):
            self.state = StrategyCapacityState.UNDER_CAPACITY
        elif self.current_capital >= self.max_capacity:
            self.state = StrategyCapacityState.OVER_CAPACITY
        elif self.current_capital >= self.max_capacity * 0.95:
            self.state = StrategyCapacityState.AT_CAPACITY
        elif self.current_capital >= self.max_capacity * 0.70:
            self.state = StrategyCapacityState.APPROACHING
        elif self.current_capital >= self.optimal_capital:
            self.state = StrategyCapacityState.OPTIMAL
        else:
            self.state = StrategyCapacityState.UNDER_CAPACITY
        return self.state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity_id": self.capacity_id,
            "strategy_id": self.strategy_id,
            "optimal_capital": self.optimal_capital,
            "max_capacity": self.max_capacity,
            "effective_capacity": self.effective_capacity,
            "current_capital": self.current_capital,
            "utilization": self.utilization,
            "state": self.state.value,
            "binding_constraint": self.binding_constraint,
            "remaining_capacity": self.remaining_capacity,
            "alpha_decay_rate": self.alpha_decay_rate,
        }

    def components_dict(self) -> Dict[str, float]:
        return {
            "alpha": self.alpha_capacity,
            "market": self.market_capacity,
            "liquidity": self.liquidity_capacity,
            "execution": self.execution_capacity,
            "risk": self.risk_capacity,
            "operational": self.operational_capacity,
        }

"""
Capacity Manager — Manages capacity lifecycle and coordination between layers.

Bridges strategy capacity models, liquidity profiles, and execution
constraints into a unified capacity management workflow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capacity_intelligence import CapacityIntelligence, CapacitySnapshot, CapacityState


@dataclass
class CapacityProfile:
    """Aggregated capacity profile for a strategy."""

    strategy_id: str = ""
    optimal_capital: float = 0.0
    max_capacity: float = float("inf")
    current_capital: float = 0.0
    utilization: float = 0.0
    alpha_decay_rate: float = 0.0
    liquidity_score: float = 50.0
    avg_impact_bps: float = 0.0
    is_constrained: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "optimal_capital": self.optimal_capital,
            "max_capacity": self.max_capacity,
            "current_capital": self.current_capital,
            "utilization": self.utilization,
            "alpha_decay_rate": self.alpha_decay_rate,
            "liquidity_score": self.liquidity_score,
            "is_constrained": self.is_constrained,
        }


class CapacityManager:
    """Coordinates capacity assessment across strategies, assets, and execution."""

    def __init__(self):
        self._intelligence = CapacityIntelligence()
        self._profiles: Dict[str, CapacityProfile] = {}
        self._capacity_limits: Dict[str, float] = {}

    def register_strategy(
        self, strategy_id: str, optimal_capital: float, max_capacity: float = float("inf")
    ) -> CapacityProfile:
        profile = CapacityProfile(
            strategy_id=strategy_id,
            optimal_capital=optimal_capital,
            max_capacity=max_capacity,
        )
        self._profiles[strategy_id] = profile
        self._intelligence.context.strategy_capacities[strategy_id] = max_capacity
        return profile

    def set_asset_capacity(self, asset: str, capacity: float) -> None:
        self._capacity_limits[asset] = capacity
        self._intelligence.context.asset_capacities[asset] = capacity

    def set_liquidity_score(self, asset: str, score: float) -> None:
        self._intelligence.context.liquidity_scores[asset] = score

    def set_participation_limit(self, max_rate: float) -> None:
        self._intelligence.context.max_participation_rate = max_rate

    def set_impact_budget(self, max_bps: float) -> None:
        self._intelligence.context.impact_budget_bps = max_bps

    def assess_capacity(
        self,
        strategy_id: str,
        asset: str,
        requested_capital: float,
        avg_daily_volume: float = 0.0,
        volatility: float = 0.0,
        spread_bps: float = 0.0,
    ) -> CapacitySnapshot:
        """Assess executable capacity for a single request."""
        snapshot = self._intelligence.assess(
            strategy_id, asset, requested_capital, avg_daily_volume, volatility, spread_bps,
        )

        # Update profile
        if strategy_id in self._profiles:
            profile = self._profiles[strategy_id]
            profile.current_capital = snapshot.executable_capital
            profile.utilization = snapshot.utilization
            profile.is_constrained = snapshot.is_constrained
            profile.liquidity_score = snapshot.liquidity_score
            profile.avg_impact_bps = snapshot.expected_impact_bps

        return snapshot

    def get_profile(self, strategy_id: str) -> Optional[CapacityProfile]:
        return self._profiles.get(strategy_id)

    def constrained_strategies(self) -> List[str]:
        return [sid for sid, p in self._profiles.items() if p.is_constrained]

    def available_headroom(self, strategy_id: str) -> float:
        profile = self._profiles.get(strategy_id)
        if not profile:
            return 0.0
        return max(0.0, profile.max_capacity - profile.current_capital)

    def summary(self) -> Dict[str, Any]:
        profiles = list(self._profiles.values())
        if not profiles:
            return {"strategies": 0}
        return {
            "strategies": len(profiles),
            "constrained": len(self.constrained_strategies()),
            "avg_utilization": sum(p.utilization for p in profiles) / len(profiles),
            "total_headroom": sum(self.available_headroom(p.strategy_id) for p in profiles),
            "capacity_assessment": self._intelligence.summary(),
        }

"""
Strategy Capacity Estimator — Estimates capacity from historical data and alpha decay.

Combines backtest results, live performance, and market characteristics
to estimate real-world strategy capacity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CapacityEstimate:
    """Capacity estimation result."""

    estimate_id: str = field(default_factory=lambda: f"CE-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""

    # Estimates
    backtest_capacity: float = float("inf")
    live_capacity: float = float("inf")
    estimated_capacity: float = float("inf")
    optimal_capital: float = 0.0

    # Confidence
    confidence: float = 0.0          # 0-1 based on data quality
    data_points: int = 0

    # Alpha decay
    alpha_decay_per_doubling: float = 0.0
    expected_return_at_capacity: float = 0.0

    # Underlying drivers
    avg_turnover: float = 0.0
    avg_holding_period_days: float = 0.0
    universe_size: int = 0
    concentration: float = 0.0

    # Gap analysis
    backtest_vs_live_ratio: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "strategy_id": self.strategy_id,
            "backtest_capacity": self.backtest_capacity,
            "live_capacity": self.live_capacity,
            "estimated_capacity": self.estimated_capacity,
            "optimal_capital": self.optimal_capital,
            "confidence": self.confidence,
            "alpha_decay_per_doubling": self.alpha_decay_per_doubling,
            "backtest_vs_live_ratio": self.backtest_vs_live_ratio,
        }


class StrategyCapacityEstimator:
    """Estimates real-world strategy capacity."""

    def __init__(self):
        self._estimates: Dict[str, CapacityEstimate] = {}

    def estimate(
        self,
        strategy_id: str,
        backtest_max_capital: float = float("inf"),
        live_max_traded: float = 0.0,
        avg_daily_volume: float = 0.0,
        avg_turnover: float = 0.0,
        universe_size: int = 0,
        holding_period_days: float = 1.0,
    ) -> CapacityEstimate:
        """Estimate strategy capacity from available data."""

        # Backtest-derived capacity
        backtest_capacity = backtest_max_capital

        # Live-derived: participation-based
        live_capacity = float("inf")
        if avg_daily_volume > 0 and avg_turnover > 0:
            # 10% participation as reasonable cap
            live_capacity = avg_daily_volume * 0.10 * holding_period_days / max(avg_turnover, 0.01)

        # Synthesis: most conservative
        estimated = min(backtest_capacity, live_capacity)

        # Optimal is typically 40-60% of max
        optimal = estimated * 0.50 if estimated < float("inf") else 0.0

        # Confidence based on data availability
        confidence = min(1.0, (live_max_traded / max(estimated, 1)) * 0.5 + 0.3) if estimated < float("inf") else 0.3

        est = CapacityEstimate(
            strategy_id=strategy_id,
            backtest_capacity=backtest_capacity,
            live_capacity=live_capacity,
            estimated_capacity=estimated,
            optimal_capital=optimal,
            confidence=confidence,
            avg_turnover=avg_turnover,
            avg_holding_period_days=holding_period_days,
            universe_size=universe_size,
            backtest_vs_live_ratio=backtest_capacity / max(live_capacity, 1) if live_capacity < float("inf") else 1.0,
        )

        self._estimates[strategy_id] = est
        return est

    def get(self, strategy_id: str) -> Optional[CapacityEstimate]:
        return self._estimates.get(strategy_id)

    def summary(self) -> Dict[str, Any]:
        return {
            "estimated_strategies": len(self._estimates),
            "avg_capacity": sum(e.estimated_capacity for e in self._estimates.values() if e.estimated_capacity < float("inf")) / max(len(self._estimates), 1),
        }

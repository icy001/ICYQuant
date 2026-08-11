"""
Strategy Capacity Model — Models the relationship between capital and alpha.

Models alpha decay as capital increases: Expected Return = f(capital).
Identifies the optimal capital point where marginal return = marginal cost.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class CapitalAlphaPoint:
    """A point on the capital-alpha curve."""
    capital: float
    expected_return: float
    sharpe: float = 0.0
    marginal_return: float = 0.0


@dataclass
class CapacityCurve:
    """The capital-capacity efficiency curve."""

    curve_id: str = field(default_factory=lambda: f"CC-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    points: List[CapitalAlphaPoint] = field(default_factory=list)

    def add_point(self, capital: float, expected_return: float, sharpe: float = 0.0) -> None:
        marginal = 0.0
        if self.points:
            last = self.points[-1]
            delta_cap = capital - last.capital
            delta_ret = expected_return - last.expected_return
            marginal = delta_ret / max(delta_cap, 1.0) if delta_cap > 0 else 0.0
        self.points.append(CapitalAlphaPoint(capital, expected_return, sharpe, marginal))

    def optimal_capital(self, min_marginal_return: float = 0.02) -> float:
        """Find capital where marginal return drops below threshold."""
        for p in self.points:
            if abs(p.marginal_return) < min_marginal_return:
                return p.capital
        return self.points[-1].capital if self.points else 0.0

    def max_capacity(self, min_return: float = 0.0) -> float:
        """Capital point where expected return drops to minimum."""
        for p in self.points:
            if p.expected_return <= min_return:
                return p.capital
        return self.points[-1].capital if self.points else float("inf")

    def alpha_at(self, capital: float) -> float:
        """Interpolate expected return at given capital."""
        if not self.points:
            return 0.0
        for i, p in enumerate(self.points):
            if p.capital >= capital:
                if i == 0:
                    return p.expected_return
                prev = self.points[i - 1]
                ratio = (capital - prev.capital) / max(p.capital - prev.capital, 1)
                return prev.expected_return + ratio * (p.expected_return - prev.expected_return)
        return self.points[-1].expected_return

    def to_dict(self) -> Dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "strategy_id": self.strategy_id,
            "points": [{"capital": p.capital, "return": p.expected_return, "sharpe": p.sharpe} for p in self.points],
        }


class StrategyCapacityModel:
    """Models and estimates strategy capacity from alpha decay characteristics."""

    def __init__(self, strategy_id: str = ""):
        self.strategy_id = strategy_id
        self._curve = CapacityCurve(strategy_id=strategy_id)
        self._base_return: float = 0.20   # return at minimal capital
        self._decay_factor: float = 0.05   # alpha decay per doubling of capital

    def build_curve(self, base_capital: float = 1.0, max_capital: float = 100.0,
                    steps: int = 20) -> CapacityCurve:
        """Build alpha-decay curve."""
        self._curve = CapacityCurve(strategy_id=self.strategy_id)
        for i in range(steps + 1):
            capital = base_capital + (max_capital - base_capital) * i / steps
            # Alpha decay: Return = BaseReturn * (BaseCapital / Capital)^decay_factor
            expected_return = self._base_return * (base_capital / max(capital, 1)) ** self._decay_factor
            sharpe = max(0, expected_return / 0.15)
            self._curve.add_point(capital, expected_return, sharpe)
        return self._curve

    def estimate_capacity(self, base_capital: float = 1.0, max_capital: float = 100.0,
                          min_return: float = 0.05) -> Tuple[float, float]:
        """Estimate optimal and max capacity from the curve."""
        self.build_curve(base_capital, max_capital)
        optimal = self._curve.optimal_capital(min_marginal_return=0.02)
        max_cap = self._curve.max_capacity(min_return)
        return optimal, max_cap

    @property
    def curve(self) -> CapacityCurve:
        return self._curve

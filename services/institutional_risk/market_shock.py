"""MarketShock — market-level price shock simulation.

Simulates market-wide price drops and computes strategy/portfolio/
capital-level impacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarketShockResult:
    """Result of a market shock simulation."""

    shock_pct: float = 0.0
    portfolio_loss: float = 0.0
    portfolio_loss_pct: float = 0.0
    strategy_impacts: Dict[str, float] = field(default_factory=dict)
    capital_remaining: float = 0.0
    beta_adjusted: bool = True
    worst_strategy: str = ""
    worst_strategy_loss: float = 0.0


class MarketShockSimulator:
    """Simulates market-level price shocks.

    Usage::

        sim = MarketShockSimulator()
        result = sim.simulate(
            shock_pct=-15.0,
            capital=100_000_000,
            strategy_betas={"strat_A": 1.2, "strat_B": 0.8},
            allocations={"strat_A": 30_000_000, "strat_B": 25_000_000},
        )
    """

    def simulate(
        self,
        shock_pct: float,
        capital: float,
        strategy_betas: Dict[str, float],
        allocations: Dict[str, float],
        use_leverage: bool = True,
    ) -> MarketShockResult:
        """Simulate a market shock.

        Args:
            shock_pct: market shock percentage (negative for drop)
            capital: total capital
            strategy_betas: {strategy_id: beta_to_market}
            allocations: {strategy_id: allocated_capital}
            use_leverage: whether to apply leverage multipliers
        """
        shock = shock_pct / 100.0
        total_loss = 0.0
        strategy_impacts: Dict[str, float] = {}
        worst_sid = ""
        worst_loss = 0.0

        for sid in allocations:
            beta = strategy_betas.get(sid, 1.0)
            allocation = allocations[sid]
            impact = allocation * beta * shock
            strategy_impacts[sid] = impact
            total_loss += impact

            if abs(impact) > abs(worst_loss):
                worst_loss = impact
                worst_sid = sid

        result = MarketShockResult(
            shock_pct=shock_pct,
            portfolio_loss=total_loss,
            portfolio_loss_pct=(total_loss / capital * 100) if capital > 0 else 0.0,
            strategy_impacts=strategy_impacts,
            capital_remaining=capital + total_loss,
            worst_strategy=worst_sid,
            worst_strategy_loss=worst_loss,
        )
        return result

    def simulate_multiple(
        self,
        shock_levels: List[float],
        capital: float,
        strategy_betas: Dict[str, float],
        allocations: Dict[str, float],
    ) -> List[MarketShockResult]:
        """Simulate multiple shock levels."""
        return [
            self.simulate(level, capital, strategy_betas, allocations)
            for level in shock_levels
        ]

    def find_breakeven_shock(
        self,
        capital: float,
        strategy_betas: Dict[str, float],
        allocations: Dict[str, float],
        tolerance: float = 0.5,
    ) -> float:
        """Find the market shock level that depletes all capital."""
        lo, hi = -100.0, 0.0
        for _ in range(50):
            mid = (lo + hi) / 2
            result = self.simulate(mid, capital, strategy_betas, allocations)
            remaining_pct = result.capital_remaining / capital * 100
            if abs(remaining_pct) < tolerance:
                return mid
            if remaining_pct > 0:
                lo = mid
            else:
                hi = mid
        return lo

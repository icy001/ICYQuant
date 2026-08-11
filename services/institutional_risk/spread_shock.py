"""SpreadShock — bid-ask spread widening simulation.

Simulates spread widening and its impact on transaction costs,
exit costs, and capital survival.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SpreadShockResult:
    """Result of a spread shock simulation."""

    spread_increase_pct: float = 0.0
    original_spread_bps: float = 0.0
    shocked_spread_bps: float = 0.0
    estimated_exit_cost: float = 0.0
    exit_cost_increase: float = 0.0
    cost_as_pct_of_capital: float = 0.0
    critical: bool = False


class SpreadShockSimulator:
    """Simulates bid-ask spread widening.

    Directly connected to Part 1.3 execution costs.
    Spread shocks can dramatically increase exit costs.

    Usage::

        sim = SpreadShockSimulator()
        result = sim.simulate(
            spread_increase_pct=100.0,
            original_spread_bps=2.0,
            portfolio_value=50_000_000,
            capital=100_000_000,
        )
        print(f"Exit cost: {result.estimated_exit_cost:.0f}")
    """

    def __init__(self, critical_cost_pct: float = 5.0):
        self._critical_threshold = critical_cost_pct

    def simulate(
        self,
        spread_increase_pct: float,
        original_spread_bps: float,
        portfolio_value: float,
        capital: float,
        turnover_ratio: float = 1.0,
    ) -> SpreadShockResult:
        """Simulate a spread shock.

        Args:
            spread_increase_pct: spread increase % (e.g., 100 = doubled)
            original_spread_bps: current spread in basis points
            portfolio_value: value of positions that need to be exited
            capital: total capital pool
            turnover_ratio: fraction of portfolio that needs trading
        """
        spread_factor = 1.0 + spread_increase_pct / 100.0
        shocked_spread = original_spread_bps * spread_factor

        # half-spread cost per unit traded
        original_half_spread_cost = (original_spread_bps / 10000) * 0.5
        shocked_half_spread_cost = (shocked_spread / 10000) * 0.5

        # exit cost = portfolio_value * turnover * half_spread_cost
        original_exit_cost = portfolio_value * turnover_ratio * original_half_spread_cost
        shocked_exit_cost = portfolio_value * turnover_ratio * shocked_half_spread_cost

        exit_cost_increase = shocked_exit_cost - original_exit_cost
        cost_as_pct = (shocked_exit_cost / max(capital, 1e-9)) * 100

        critical = cost_as_pct > self._critical_threshold

        return SpreadShockResult(
            spread_increase_pct=spread_increase_pct,
            original_spread_bps=original_spread_bps,
            shocked_spread_bps=shocked_spread,
            estimated_exit_cost=shocked_exit_cost,
            exit_cost_increase=exit_cost_increase,
            cost_as_pct_of_capital=cost_as_pct,
            critical=critical,
        )

    def compute_spread_impact_on_survival(
        self,
        spread_result: SpreadShockResult,
        current_survival_score: float,
    ) -> float:
        """Adjust survival score for spread shock impact."""
        # each 1% of capital in exit costs reduces survival by ~2 points
        penalty = spread_result.cost_as_pct_of_capital * 2.0
        return max(0.0, current_survival_score - penalty)

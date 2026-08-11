"""CorrelationShock — correlation spike shock simulation.

Simulates scenarios where pairwise correlations increase,
causing diversification to fail and portfolio risk to surge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CorrelationShockResult:
    """Result of a correlation shock simulation."""

    corr_increase_pct: float = 0.0
    original_avg_corr: float = 0.0
    shocked_avg_corr: float = 0.0
    original_portfolio_risk: float = 0.0
    shocked_portfolio_risk: float = 0.0
    risk_increase_pct: float = 0.0
    diversification_erosion_pct: float = 0.0
    pairs_over_threshold: int = 0
    needs_rebalancing: bool = False


class CorrelationShockSimulator:
    """Simulates correlation spike impacts.

    When correlations jump, portfolio risk can increase
    substantially even if individual strategy risks are unchanged.

    Usage::

        sim = CorrelationShockSimulator()
        result = sim.simulate(
            corr_increase_pct=40.0,  # +40% correlation
            current_avg_corr=0.25,
            current_portfolio_risk=8_000_000,
            strategy_risks={"A": 3_000_000, "B": 2_500_000, "C": 2_500_000},
            n_assets=3,
        )
        print(f"Risk increases by {result.risk_increase_pct:.0f}%")
    """

    def __init__(self, high_corr_threshold: float = 0.70):
        self._high_threshold = high_corr_threshold

    def simulate(
        self,
        corr_increase_pct: float,
        current_avg_corr: float,
        current_portfolio_risk: float,
        strategy_risks: Optional[Dict[str, float]] = None,
        n_assets: int = 1,
        current_pairwise: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> CorrelationShockResult:
        """Simulate a correlation shock.

        Portfolio variance: σ²_p = Σ w_i² σ_i² + Σ Σ w_i w_j σ_i σ_j ρ_ij
        As ρ_ij → 1, portfolio risk → Σ w_i σ_i (no diversification).

        Args:
            corr_increase_pct: correlation increase percentage (+40 = 40% increase)
            current_avg_corr: current average pairwise correlation
            current_portfolio_risk: current portfolio VaR
            strategy_risks: {strategy_id: individual_var}
            n_assets: number of strategies
            current_pairwise: current pairwise correlations
        """
        corr_factor = 1.0 + corr_increase_pct / 100.0
        shocked_avg_corr = min(current_avg_corr * corr_factor, 0.99)

        # portfolio risk scaling with correlation
        # σ_new = σ_old * sqrt((1 + (n-1)*ρ_new) / (1 + (n-1)*ρ_old))
        n = max(n_assets, max(len(strategy_risks) if strategy_risks else 1, 1))

        if n == 1:
            risk_increase = 0.0
            shocked_risk = current_portfolio_risk
        else:
            old_factor = 1.0 + (n - 1) * current_avg_corr
            new_factor = 1.0 + (n - 1) * shocked_avg_corr
            if old_factor > 0:
                risk_multiplier = math.sqrt(new_factor / old_factor)
            else:
                risk_multiplier = 1.0

            shocked_risk = current_portfolio_risk * risk_multiplier
            risk_increase = (risk_multiplier - 1.0) * 100

        # diversification erosion
        # original diversification benefit = 1 - sqrt((1+(n-1)*ρ)/n)
        def div_benefit(corr: float) -> float:
            return 1.0 - math.sqrt((1 + (n - 1) * corr) / n)

        original_div = div_benefit(current_avg_corr)
        shocked_div = div_benefit(shocked_avg_corr)
        erosion = 0.0
        if original_div > 0:
            erosion = (original_div - shocked_div) / original_div * 100

        # pairs over threshold
        pairs_over = 0
        if current_pairwise:
            for pair, corr in current_pairwise.items():
                shocked_pair_corr = min(corr * corr_factor, 0.99)
                if shocked_pair_corr > self._high_threshold:
                    pairs_over += 1

        needs_rebalance = risk_increase > 15.0

        return CorrelationShockResult(
            corr_increase_pct=corr_increase_pct,
            original_avg_corr=current_avg_corr,
            shocked_avg_corr=shocked_avg_corr,
            original_portfolio_risk=current_portfolio_risk,
            shocked_portfolio_risk=shocked_risk,
            risk_increase_pct=risk_increase,
            diversification_erosion_pct=erosion,
            pairs_over_threshold=pairs_over,
            needs_rebalancing=needs_rebalance,
        )

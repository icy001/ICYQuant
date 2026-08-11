"""ExtremeLoss — extreme loss modeling and worst-case analysis.

Estimates worst-case losses using extreme value theory concepts,
going beyond simple VaR to model the tail distribution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtremeLossResult:
    """Extreme loss analysis result."""

    entity_id: str
    worst_observed: float = 0.0
    var_99: float = 0.0
    var_999: float = 0.0
    expected_shortfall_99: float = 0.0
    expected_shortfall_999: float = 0.0
    max_drawdown: float = 0.0
    extreme_loss_estimate: float = 0.0  # EVT-based estimate
    return_period_days: int = 0  # days between extreme losses
    tail_index: float = 0.0  # Hill estimator
    tail_fatness: str = "NORMAL"


class ExtremeLossEstimator:
    """Estimates extreme losses beyond historical observations.

    Uses Hill estimator for tail index and provides EVT-based
    loss estimates for rare events.

    Usage::

        estimator = ExtremeLossEstimator()
        result = estimator.estimate("strategy_A", daily_returns)
        print(f"1-in-1000 day loss: {result.extreme_loss_estimate:.0f}")
    """

    def __init__(self, tail_fraction: float = 0.05):
        self._tail_fraction = tail_fraction

    def estimate(
        self,
        entity_id: str,
        returns: List[float],
        confidence: float = 0.999,
    ) -> ExtremeLossResult:
        """Estimate extreme losses.

        Args:
            entity_id: strategy/portfolio id
            returns: return series (losses as positive numbers)
            confidence: extreme confidence level (e.g., 0.999)
        """
        if len(returns) < 50:
            return ExtremeLossResult(entity_id=entity_id)

        n = len(returns)
        sorted_returns = sorted(returns, reverse=True)  # descending

        # basic metrics
        worst = min(returns)
        var_99 = abs(sorted_returns[int(n * 0.01)]) if n > 100 else worst
        var_999 = abs(sorted_returns[int(n * 0.001)]) if n > 1000 else worst * 1.5

        # ES
        es_99 = 0.0
        tail_99 = [r for r in returns if r < -var_99]
        if tail_99:
            es_99 = abs(sum(tail_99) / len(tail_99))

        es_999 = es_99 * 1.5  # rough extrapolation

        # max drawdown approximation
        peak = 0.0
        max_dd = 0.0
        cumulative = 0.0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / max(abs(peak), 1e-9) * 100
            max_dd = max(max_dd, dd)

        # Hill estimator for tail index
        tail_size = max(int(n * self._tail_fraction), 10)
        tail_data = sorted([abs(r) for r in returns if r < 0])
        if len(tail_data) >= tail_size:
            tail_data = tail_data[-tail_size:]
            threshold = tail_data[0]
            # Hill estimator: 1/α = (1/k) * Σ log(X_i / threshold)
            hill_sum = sum(math.log(x / max(threshold, 1e-9)) for x in tail_data[1:])
            hill_alpha = (len(tail_data) - 1) / max(hill_sum, 1e-9)
        else:
            hill_alpha = 3.0  # default moderate tail

        # EVT-based extreme loss estimate
        # For Pareto tail: P(X > x) ≈ (x/threshold)^(-α)
        extreme_estimate = var_99 * ((1 - confidence) / 0.01) ** (-1.0 / hill_alpha)

        # tail fatness classification
        fatness = "NORMAL"
        if hill_alpha < 2:
            fatness = "EXTREME"
        elif hill_alpha < 3:
            fatness = "FAT"
        elif hill_alpha < 4:
            fatness = "MODERATE"

        # return period
        return_period = int(1.0 / max(1 - confidence, 1e-9))

        return ExtremeLossResult(
            entity_id=entity_id,
            worst_observed=abs(worst),
            var_99=var_99,
            var_999=var_999,
            expected_shortfall_99=es_99,
            expected_shortfall_999=es_999,
            max_drawdown=max_dd,
            extreme_loss_estimate=extreme_estimate,
            return_period_days=return_period,
            tail_index=hill_alpha,
            tail_fatness=fatness,
        )

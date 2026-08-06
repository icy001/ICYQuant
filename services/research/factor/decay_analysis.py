"""Decay Analysis — analyze alpha signal decay over time.

Supports::

    1 Day, 5 Day, 10 Day, 20 Day, 60 Day forward horizons

Measures how quickly a factor's predictive power diminishes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecayResult:
    """Decay analysis result."""

    factor_name: str = ""
    horizons: List[int] = field(default_factory=list)
    ic_by_horizon: Dict[int, float] = field(default_factory=dict)
    rankic_by_horizon: Dict[int, float] = field(default_factory=dict)
    half_life: Optional[int] = None  # days until IC drops to half
    decay_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "horizons": self.horizons,
            "ic_by_horizon": self.ic_by_horizon,
            "rankic_by_horizon": self.rankic_by_horizon,
            "half_life": self.half_life,
            "decay_rate": self.decay_rate,
            "metadata": self.metadata,
        }


class DecayAnalyzer:
    """Alpha signal decay analysis.

    Computes IC/RankIC at multiple forward horizons to measure
    how quickly predictive power decays over time.

    Default horizons: [1, 5, 10, 20, 60] days
    """

    DEFAULT_HORIZONS = [1, 5, 10, 20, 60]

    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        min_periods: int = 20,
    ) -> None:
        self._horizons = horizons or self.DEFAULT_HORIZONS
        self._min_periods = min_periods

    def analyze(
        self,
        factor_panel: Dict[str, List[float]],
        forward_returns_by_horizon: Dict[int, Dict[str, List[float]]],
        factor_name: str = "",
    ) -> DecayResult:
        """Analyze factor decay across multiple horizons.

        Args:
            factor_panel: date → factor values
            forward_returns_by_horizon: horizon → (date → forward returns)
            factor_name: factor identifier

        Returns:
            DecayResult with IC at each horizon
        """
        result = DecayResult(
            factor_name=factor_name,
            horizons=list(self._horizons),
        )

        for horizon in self._horizons:
            if horizon not in forward_returns_by_horizon:
                continue

            returns_panel = forward_returns_by_horizon[horizon]
            dates = sorted(set(factor_panel.keys()) & set(returns_panel.keys()))

            daily_ic: List[float] = []
            daily_rankic: List[float] = []

            for date in dates:
                f_vals = factor_panel.get(date, [])
                r_vals = returns_panel.get(date, [])
                if not f_vals or not r_vals:
                    continue

                n = min(len(f_vals), len(r_vals))
                if n < self._min_periods:
                    continue

                # Pearson IC
                mean_f = sum(f_vals[:n]) / n
                mean_r = sum(r_vals[:n]) / n
                cov = sum(
                    (f - mean_f) * (r - mean_r)
                    for f, r in zip(f_vals[:n], r_vals[:n])
                )
                var_f = sum((f - mean_f) ** 2 for f in f_vals[:n])
                var_r = sum((r - mean_r) ** 2 for r in r_vals[:n])

                if var_f > 0 and var_r > 0:
                    ic = cov / ((var_f * var_r) ** 0.5)
                    daily_ic.append(ic)

            if daily_ic:
                result.ic_by_horizon[horizon] = sum(daily_ic) / len(daily_ic)

            if daily_rankic:
                result.rankic_by_horizon[horizon] = sum(daily_rankic) / len(daily_rankic)

        # Compute half-life: days until IC drops to half of initial
        result.half_life = self._compute_half_life(result.ic_by_horizon)

        # Compute decay rate (exponential fit)
        result.decay_rate = self._compute_decay_rate(result.ic_by_horizon)

        return result

    def _compute_half_life(self, ic_by_horizon: Dict[int, float]) -> Optional[int]:
        """Estimate half-life from IC decay curve."""
        if not ic_by_horizon:
            return None

        sorted_horizons = sorted(ic_by_horizon.keys())
        initial_ic = abs(ic_by_horizon.get(sorted_horizons[0], 0.0))
        if initial_ic == 0:
            return None

        half_target = initial_ic / 2

        for h in sorted_horizons:
            if abs(ic_by_horizon.get(h, 0.0)) <= half_target:
                return h

        return None

    def _compute_decay_rate(self, ic_by_horizon: Dict[int, float]) -> float:
        """Compute exponential decay rate."""
        if len(ic_by_horizon) < 2:
            return 0.0

        sorted_items = sorted(ic_by_horizon.items())
        h1, ic1 = sorted_items[0]
        h_last, ic_last = sorted_items[-1]

        if abs(ic1) < 1e-10 or h_last == h1:
            return 0.0

        # Exponential: IC(t) = IC0 * exp(-lambda * t)
        # lambda = -ln(IC(t)/IC0) / t
        import math
        ic_ratio = abs(ic_last) / abs(ic1)
        if ic_ratio <= 0:
            return 0.0

        return -math.log(ic_ratio) / (h_last - h1)

    def decay_summary(self, result: DecayResult) -> Dict[str, Any]:
        """Generate a human-readable decay summary."""
        return {
            "factor_name": result.factor_name,
            "initial_ic": result.ic_by_horizon.get(1, 0.0),
            "ic_after_20d": result.ic_by_horizon.get(20, 0.0),
            "half_life_days": result.half_life,
            "decay_rate": f"{result.decay_rate:.6f}",
            "persistence": "high" if result.half_life and result.half_life > 30
            else "medium" if result.half_life and result.half_life > 10
            else "low",
        }

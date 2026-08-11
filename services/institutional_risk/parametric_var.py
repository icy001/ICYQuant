"""ParametricVar — parametric VaR assuming normal or t-distribution.

Faster and smoother than historical VaR; useful for real-time
risk monitoring and marginal analysis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParametricVaRResult:
    """Parametric VaR result."""

    var_95: float = 0.0
    var_99: float = 0.0
    mu: float = 0.0
    sigma: float = 0.0
    sharpe: float = 0.0
    z_95: float = 1.6449
    z_99: float = 2.3263
    distribution: str = "normal"
    degrees_of_freedom: Optional[float] = None
    sample_size: int = 0


class ParametricVaREngine:
    """Parametric VaR engine supporting Normal and Student-t distributions.

    Usage::

        engine = ParametricVaREngine()
        result = engine.compute_normal(returns)
        print(f"Parametric VaR 99%: {result.var_99:.0f}")
    """

    # Z-scores
    Z = {
        0.90: 1.2816,
        0.95: 1.6449,
        0.975: 1.9600,
        0.99: 2.3263,
        0.995: 2.5758,
        0.999: 3.0902,
    }

    # t-distribution critical values for common df and 99% (approximate)
    T_CRITICAL = {
        1: 31.82,
        2: 6.965,
        3: 4.541,
        4: 3.747,
        5: 3.365,
        10: 2.764,
        20: 2.528,
        30: 2.457,
        60: 2.390,
        120: 2.358,
        1000: 2.330,
    }

    def compute_normal(self, returns: List[float]) -> ParametricVaRResult:
        """Compute VaR assuming normal distribution.

        VaR_α = -(μ - z_α * σ)
        """
        if len(returns) < 2:
            return ParametricVaRResult()

        n = len(returns)
        mu = sum(returns) / n
        variance = sum((r - mu) ** 2 for r in returns) / (n - 1)
        sigma = math.sqrt(max(variance, 0.0))

        var_95 = max(0.0, -(mu - self.Z[0.95] * sigma))
        var_99 = max(0.0, -(mu - self.Z[0.99] * sigma))
        sharpe = mu / sigma if sigma > 0 else 0.0

        return ParametricVaRResult(
            var_95=var_95,
            var_99=var_99,
            mu=mu,
            sigma=sigma,
            sharpe=sharpe,
            z_95=self.Z[0.95],
            z_99=self.Z[0.99],
            distribution="normal",
            sample_size=n,
        )

    def compute_t(
        self,
        returns: List[float],
        df: Optional[float] = None,
    ) -> ParametricVaRResult:
        """Compute VaR assuming Student-t distribution (fatter tails).

        Args:
            returns: list of returns
            df: degrees of freedom (auto-estimated if None)
        """
        if len(returns) < 5:
            return self.compute_normal(returns)

        n = len(returns)
        mu = sum(returns) / n
        variance = sum((r - mu) ** 2 for r in returns) / (n - 1)
        sigma = math.sqrt(max(variance, 0.0))

        if df is None:
            # estimate df from kurtosis: kurt = 6/(df-4) + 3 for t-dist
            kurt = 0.0
            if sigma > 0:
                kurt = sum(((r - mu) / sigma) ** 4 for r in returns) / n
            if kurt > 3:
                df = 6 / (kurt - 3) + 4
            else:
                df = 100.0  # near-normal

        df = max(1.0, min(df, 1000.0))

        # interpolate t-critical value
        t_crit = self._get_t_critical(df)
        t_crit_95 = t_crit * (self.Z[0.95] / self.Z[0.99])

        var_95 = max(0.0, -(mu - t_crit_95 * sigma))
        var_99 = max(0.0, -(mu - t_crit * sigma))
        sharpe = mu / sigma if sigma > 0 else 0.0

        return ParametricVaRResult(
            var_95=var_95,
            var_99=var_99,
            mu=mu,
            sigma=sigma,
            sharpe=sharpe,
            z_95=t_crit_95,
            z_99=t_crit,
            distribution="student-t",
            degrees_of_freedom=df,
            sample_size=n,
        )

    def _get_t_critical(self, df: float) -> float:
        """Get approximate t-critical value for 99% confidence."""
        if df in self.T_CRITICAL:
            return self.T_CRITICAL[df]

        # interpolate
        sorted_df = sorted(self.T_CRITICAL.items())
        for i in range(len(sorted_df) - 1):
            if sorted_df[i][0] <= df <= sorted_df[i + 1][0]:
                ratio = (df - sorted_df[i][0]) / (sorted_df[i + 1][0] - sorted_df[i][0])
                return sorted_df[i][1] + ratio * (sorted_df[i + 1][1] - sorted_df[i][1])

        return 2.3263  # default to normal

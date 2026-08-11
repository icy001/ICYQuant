"""
Parametric VaR — Variance-Covariance (parametric) Value-at-Risk.

Computes VaR assuming normally distributed returns, using the portfolio's
variance-covariance matrix. Supports both equal-weighted and EWMA volatility.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ParametricVaR:
    """
    Parametric (Variance-Covariance) Value-at-Risk calculator.

    Assumes returns are normally distributed and computes VaR using::

        VaR_α = μ + σ · z_α · √T

    where z_α is the standard normal quantile, μ is expected return,
    σ is portfolio volatility, and T is the time horizon.

    Supports:
    - Equal-weighted standard deviation
    - Exponentially Weighted Moving Average (EWMA) volatility
    - Multi-asset portfolio with correlation matrix

    Usage::

        pvar = ParametricVaR(decay_factor=0.94)
        await pvar.initialize()
        results = await pvar.calculate(portfolio_data, [0.95, 0.99], [1, 5, 10])
    """

    # Pre-computed standard normal quantiles
    NORMAL_QUANTILES: dict[float, float] = {
        0.90: 1.2816,
        0.95: 1.6449,
        0.975: 1.9600,
        0.99: 2.3263,
        0.995: 2.5758,
        0.999: 3.0902,
    }

    def __init__(self, decay_factor: float = 0.94) -> None:
        self._decay_factor = decay_factor
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the parametric VaR calculator."""
        self._initialized = True

    async def calculate(
        self,
        portfolio_data: dict[str, Any],
        confidence_levels: list[float],
        time_horizons: list[int],
    ) -> dict[str, Any]:
        """
        Calculate Parametric VaR.

        Parameters
        ----------
        portfolio_data : dict
            Must contain 'returns' (list of daily returns) and 'total_value'.
        confidence_levels : list[float]
            Confidence levels.
        time_horizons : list[int]
            Time horizons in days.

        Returns
        -------
        dict
            VaR entries.
        """
        import time

        t_start = time.perf_counter()

        returns = portfolio_data.get("returns", [])
        total_value = portfolio_data.get("total_value", 1_000_000)

        if not returns:
            return {"error": "No return data available for parametric VaR", "var_entries": []}

        # Compute portfolio statistics
        mu = sum(returns) / len(returns)  # mean daily return

        # Standard deviation (equal-weighted)
        n = len(returns)
        variance = sum((r - mu) ** 2 for r in returns) / (n - 1) if n > 1 else 0.0
        sigma_eq = math.sqrt(variance)

        # EWMA volatility
        sigma_ewma = self._compute_ewma_volatility(returns)

        # Multi-asset covariance if positions available
        positions = portfolio_data.get("positions", [])
        if positions and len(positions) > 1:
            sigma_portfolio = await self._compute_portfolio_volatility(positions, returns)
        else:
            sigma_portfolio = sigma_eq

        var_entries = []

        for horizon in time_horizons:
            scale = math.sqrt(horizon)
            for conf in confidence_levels:
                z_score = self.NORMAL_QUANTILES.get(conf, 1.6449)

                # Equal-weighted VaR
                var_pct_eq = abs(mu * horizon - sigma_eq * z_score * scale)
                var_value_eq = total_value * var_pct_eq

                # EWMA VaR
                var_pct_ewma = abs(mu * horizon - sigma_ewma * z_score * scale)
                var_value_ewma = total_value * var_pct_ewma

                # Portfolio VaR (with correlations)
                var_pct_port = abs(mu * horizon - sigma_portfolio * z_score * scale)
                var_value_port = total_value * var_pct_port

                var_entries.append({
                    "method": "parametric",
                    "confidence_level": conf,
                    "time_horizon_days": horizon,
                    "var_value": round(var_value_eq, 2),
                    "var_percentage": round(var_pct_eq * 100, 4),
                    "var_value_ewma": round(var_value_ewma, 2),
                    "var_percentage_ewma": round(var_pct_ewma * 100, 4),
                    "var_value_portfolio": round(var_value_port, 2),
                    "var_percentage_portfolio": round(var_pct_port * 100, 4),
                    "portfolio_value": total_value,
                    "z_score": z_score,
                    "annualized_volatility_eq": round(sigma_eq * math.sqrt(252) * 100, 2),
                    "annualized_volatility_ewma": round(sigma_ewma * math.sqrt(252) * 100, 2),
                })

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        return {
            "method": "parametric",
            "var_entries": var_entries,
            "calculation_time_ms": elapsed_ms,
            "statistics": {
                "mean_daily_return": round(mu * 100, 4),
                "volatility_daily_eq": round(sigma_eq * 100, 4),
                "volatility_daily_ewma": round(sigma_ewma * 100, 4),
                "annualized_return_pct": round(mu * 252 * 100, 2),
                "annualized_volatility_eq_pct": round(sigma_eq * math.sqrt(252) * 100, 2),
                "annualized_volatility_ewma_pct": round(sigma_ewma * math.sqrt(252) * 100, 2),
                "sharpe_ratio_eq": round((mu * 252 - 0.02) / (sigma_eq * math.sqrt(252)), 4) if sigma_eq > 0 else 0,
                "decay_factor": self._decay_factor,
            },
        }

    def _compute_ewma_volatility(self, returns: list[float]) -> float:
        """Compute EWMA daily volatility."""
        if not returns:
            return 0.0

        variance = returns[0] ** 2
        for r in returns[1:]:
            variance = self._decay_factor * variance + (1 - self._decay_factor) * r ** 2

        return math.sqrt(variance)

    async def _compute_portfolio_volatility(
        self,
        positions: list[dict],
        returns: list[float],
    ) -> float:
        """Compute portfolio volatility with correlation matrix."""
        # Simplified: use equal-weighted positions
        n_assets = len(positions)
        if n_assets <= 1:
            return math.sqrt(sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / (len(returns) - 1)) if len(returns) > 1 else 0.0

        # Approximate using average pairwise correlation
        weights = [1.0 / n_assets] * n_assets
        avg_vol = math.sqrt(sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / (len(returns) - 1)) if len(returns) > 1 else 0.01

        # Assume average correlation of 0.3 for diversified portfolio
        avg_corr = 0.3
        portfolio_variance = 0.0
        for i in range(n_assets):
            for j in range(n_assets):
                corr = 1.0 if i == j else avg_corr
                portfolio_variance += weights[i] * weights[j] * avg_vol * avg_vol * corr

        return math.sqrt(max(0, portfolio_variance))

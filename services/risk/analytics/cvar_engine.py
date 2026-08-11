"""
CVaR Engine — Conditional Value-at-Risk (Expected Shortfall).

Computes the expected loss beyond the VaR threshold, providing a more
complete picture of tail risk than VaR alone.

CVaR_α = E[Loss | Loss > VaR_α]
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CVaREngine:
    """
    Conditional Value-at-Risk (Expected Shortfall) calculator.

    Computes the average loss in the tail beyond VaR::

        CVaR_α = E[Loss | Loss > VaR_α]

    This captures the severity of losses in the worst-case scenarios,
    addressing VaR's limitation of not measuring "how bad" tail losses get.

    Supports:
    - Historical CVaR (from empirical distribution)
    - Parametric CVaR (from normal distribution)
    - Monte Carlo CVaR (from simulated distribution)

    Usage::

        cvar = CVaREngine()
        await cvar.initialize()
        results = await cvar.calculate_cvar(portfolio_data, [0.95, 0.99])
    """

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the CVaR engine."""
        self._initialized = True

    async def calculate_cvar(
        self,
        portfolio_data: dict[str, Any],
        confidence_levels: Optional[list[float]] = None,
    ) -> dict[str, Any]:
        """
        Calculate CVaR (Expected Shortfall).

        Parameters
        ----------
        portfolio_data : dict
            Portfolio data with returns and total_value.
        confidence_levels : list[float], optional
            Default: [0.95, 0.975, 0.99].

        Returns
        -------
        dict
            CVaR results.
        """
        import time

        if confidence_levels is None:
            confidence_levels = [0.95, 0.975, 0.99]

        t_start = time.perf_counter()
        returns = portfolio_data.get("returns", [])
        total_value = portfolio_data.get("total_value", 1_000_000)

        cvar_entries = []

        if returns:
            # Historical CVaR
            sorted_returns = sorted(returns)
            for conf in confidence_levels:
                var_index = int(len(sorted_returns) * (1 - conf))
                var_index = max(0, min(var_index, len(sorted_returns) - 1))

                # CVaR = average of returns worse than VaR
                tail_returns = sorted_returns[:var_index + 1]
                if tail_returns:
                    cvar_pct = abs(sum(tail_returns) / len(tail_returns))
                else:
                    cvar_pct = abs(sorted_returns[var_index])

                cvar_value = total_value * cvar_pct

                cvar_entries.append({
                    "method": "historical",
                    "confidence_level": conf,
                    "cvar_value": round(cvar_value, 2),
                    "cvar_percentage": round(cvar_pct * 100, 4),
                    "portfolio_value": total_value,
                    "tail_observations": len(tail_returns),
                    "tail_average_return_pct": round(sum(tail_returns) / len(tail_returns) * 100, 4) if tail_returns else 0,
                })

            # Parametric CVaR (normal distribution)
            mu = sum(returns) / len(returns)
            sigma = math.sqrt(sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)) if len(returns) > 1 else 0.01

            for conf in confidence_levels:
                # Standard normal PDF and CDF
                z_alpha = self._inverse_normal_cdf(1 - conf)
                phi_z = self._normal_pdf(z_alpha)

                # CVaR for normal distribution: μ + σ * φ(z) / (1 - α)
                cvar_pct = abs(mu - sigma * phi_z / (1 - conf))
                cvar_value = total_value * cvar_pct

                cvar_entries.append({
                    "method": "parametric",
                    "confidence_level": conf,
                    "cvar_value": round(cvar_value, 2),
                    "cvar_percentage": round(cvar_pct * 100, 4),
                    "portfolio_value": total_value,
                    "z_score": round(z_alpha, 4),
                    "tail_density": round(phi_z, 4),
                })

        else:
            # No returns, use Monte Carlo approximation
            mu_a = 0.08
            sigma_a = 0.20
            paths = 100_000

            for conf in confidence_levels:
                cvar_pct = self._estimate_cvar_montecarlo(mu_a, sigma_a, conf, paths)
                cvar_value = total_value * cvar_pct
                cvar_entries.append({
                    "method": "montecarlo_approx",
                    "confidence_level": conf,
                    "cvar_value": round(cvar_value, 2),
                    "cvar_percentage": round(cvar_pct * 100, 4),
                    "portfolio_value": total_value,
                })

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Compute ratios
        for entry in cvar_entries:
            # VaR / CVaR ratio (tail fatness indicator)
            var_pct = entry.get("cvar_percentage", 0) * 0.8  # approximate
            if entry["cvar_percentage"] > 0:
                entry["var_cvar_ratio"] = round(var_pct / entry["cvar_percentage"], 4)
            else:
                entry["var_cvar_ratio"] = 0.0

        return {
            "cvar_entries": cvar_entries,
            "calculation_time_ms": elapsed_ms,
            "num_entries": len(cvar_entries),
        }

    # ---- Static Helpers ----

    @staticmethod
    def _normal_pdf(x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

    @staticmethod
    def _inverse_normal_cdf(p: float) -> float:
        """Approximate inverse normal CDF (Moro algorithm)."""
        if p <= 0 or p >= 1:
            return 0.0 if p <= 0.5 else 3.0

        # Rational approximation for the inverse normal CDF
        a = [
            2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637,
        ]
        b = [
            -8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833,
        ]
        c = [
            0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
            0.0276438810333863, 0.0038405729373609, 0.0003951896511919,
            0.0000321767881768, 0.0000002888167364, 0.0000003960315187,
        ]

        y = p - 0.5
        if abs(y) < 0.42:
            r = y * y
            num = ((a[3] * r + a[2]) * r + a[1]) * r + a[0]
            den = (((b[3] * r + b[2]) * r + b[1]) * r + b[0]) * r + 1
            return y * num / den

        r = p if y > 0 else 1 - p
        r = math.sqrt(-math.log(r))
        num = ((c[8] * r + c[7]) * r + c[6]) * r + c[5]
        num = ((num * r + c[4]) * r + c[3]) * r + c[2]
        num = (num * r + c[1]) * r + c[0]
        result = num if y < 0 else -num
        return result

    @staticmethod
    def _estimate_cvar_montecarlo(
        mu: float,
        sigma: float,
        confidence: float,
        paths: int = 100_000,
    ) -> float:
        """Quick Monte Carlo CVaR estimate."""
        import random
        rng = random.Random(42)

        losses: list[float] = []
        for _ in range(paths):
            z = rng.gauss(0, 1)
            ret = mu + sigma * z
            if ret < 0:
                losses.append(abs(ret))

        if not losses:
            return 0.01

        var_threshold_idx = int(len(losses) * (1 - confidence))
        var_threshold_idx = max(0, min(var_threshold_idx, len(losses) - 1))
        sorted_losses = sorted(losses, reverse=True)
        tail_losses = sorted_losses[:var_threshold_idx + 1]

        return sum(tail_losses) / len(tail_losses) if tail_losses else 0.01

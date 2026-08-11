"""
Monte Carlo VaR — Value-at-Risk via Monte Carlo simulation.

Computes VaR by simulating thousands of random price paths using
Geometric Brownian Motion, then computing the loss distribution.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MonteCarloVaR:
    """
    Monte Carlo Value-at-Risk calculator.

    Simulates portfolio value evolution using Geometric Brownian Motion::

        S_t = S_0 · exp((μ - σ²/2)·t + σ·√t·ε)

    where ε ~ N(0,1). VaR is computed from the simulated loss distribution.

    Usage::

        mcvar = MonteCarloVaR(paths=100_000, steps=252)
        await mcvar.initialize()
        results = await mcvar.calculate(portfolio_data, [0.95, 0.99], [1, 5, 10])
    """

    def __init__(self, paths: int = 100_000, steps: int = 252, seed: Optional[int] = None) -> None:
        self._paths = paths
        self._steps = steps
        self._rng = random.Random(seed)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Monte Carlo VaR calculator."""
        self._initialized = True

    async def calculate(
        self,
        portfolio_data: dict[str, Any],
        confidence_levels: list[float],
        time_horizons: list[int],
    ) -> dict[str, Any]:
        """
        Calculate Monte Carlo VaR.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio data with total_value, returns for drift/vol estimation.
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

        # Estimate drift and volatility
        if returns:
            mu = sum(returns) / len(returns) * 252  # annualized
            sigma = math.sqrt(
                sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / (len(returns) - 1)
            ) * math.sqrt(252) if len(returns) > 1 else 0.20
        else:
            mu = 0.08
            sigma = 0.20

        # Limit paths for performance
        paths = min(self._paths, 500_000)

        # Generate random normal samples using Box-Muller
        normals: list[float] = []
        for _ in range(paths // 2 + 1):
            u1 = self._rng.random()
            u2 = self._rng.random()
            z1 = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)
            z2 = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.sin(2 * math.pi * u2)
            normals.append(z1)
            normals.append(z2)
        normals = normals[:paths]

        var_entries = []

        for horizon in time_horizons:
            T = horizon / 252  # fraction of year
            dt = T

            # Simulate terminal values
            terminal_values: list[float] = []
            for z in normals:
                S_T = total_value * math.exp(
                    (mu - sigma ** 2 / 2) * dt + sigma * math.sqrt(dt) * z
                )
                terminal_values.append(S_T)

            # Compute losses
            losses = [total_value - tv for tv in terminal_values]
            sorted_losses = sorted(losses)

            for conf in confidence_levels:
                alpha = 1 - conf
                index = int(len(sorted_losses) * (1 - alpha))
                index = max(0, min(index, len(sorted_losses) - 1))

                var_value = sorted_losses[index]
                var_pct = var_value / total_value if total_value > 0 else 0

                var_entries.append({
                    "method": "montecarlo",
                    "confidence_level": conf,
                    "time_horizon_days": horizon,
                    "var_value": round(var_value, 2),
                    "var_percentage": round(var_pct * 100, 4),
                    "portfolio_value": total_value,
                    "num_paths": paths,
                    "drift_annualized": round(mu, 6),
                    "volatility_annualized": round(sigma, 6),
                })

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Loss distribution statistics
        if 'sorted_losses' in dir():
            loss_mean = sum(sorted_losses) / len(sorted_losses)
            loss_std = math.sqrt(
                sum((l - loss_mean) ** 2 for l in sorted_losses) / len(sorted_losses)
            )
        else:
            loss_mean = 0
            loss_std = 0

        return {
            "method": "montecarlo",
            "var_entries": var_entries,
            "calculation_time_ms": elapsed_ms,
            "simulation_parameters": {
                "num_paths": paths,
                "drift_annualized": mu,
                "volatility_annualized": sigma,
            },
            "loss_distribution": {
                "mean_loss": round(loss_mean, 2),
                "std_loss": round(loss_std, 2),
                "max_loss": round(sorted_losses[-1], 2) if 'sorted_losses' in dir() else 0,
                "min_loss": round(sorted_losses[0], 2) if 'sorted_losses' in dir() else 0,
            },
        }

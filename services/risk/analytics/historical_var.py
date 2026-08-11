"""
Historical VaR — Non-parametric Value-at-Risk using historical return distributions.

Computes VaR by analyzing the empirical distribution of historical portfolio
returns without assuming any parametric distribution.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HistoricalVaR:
    """
    Historical (non-parametric) Value-at-Risk calculator.

    Computes VaR by taking the percentile of the historical return distribution.
    This method makes no assumptions about return distributions and captures
    fat tails naturally.

    Methodology::

        Historical Returns
            │
            ▼
        Sort Returns (ascending)
            │
            ▼
        Select α-percentile
            │
            ▼
        Scale by √horizon
            │
            ▼
        VaR Value

    Usage::

        hvar = HistoricalVaR()
        await hvar.initialize()
        results = await hvar.calculate(portfolio_data, [0.95, 0.99], [1, 5, 10])
    """

    def __init__(self, window_days: int = 500) -> None:
        self._window_days = window_days
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the historical VaR calculator."""
        self._initialized = True

    async def calculate(
        self,
        portfolio_data: dict[str, Any],
        confidence_levels: list[float],
        time_horizons: list[int],
    ) -> dict[str, Any]:
        """
        Calculate Historical VaR.

        Parameters
        ----------
        portfolio_data : dict
            Must contain 'returns' (list of daily returns) or 'positions' +
            historical price data, and 'total_value'.
        confidence_levels : list[float]
            Confidence levels (e.g., [0.95, 0.99]).
        time_horizons : list[int]
            Time horizons in days (e.g., [1, 5, 10]).

        Returns
        -------
        dict
            VaR entries for each (confidence, horizon) pair.
        """
        import time

        t_start = time.perf_counter()

        # Get historical returns
        returns = portfolio_data.get("returns", [])
        if not returns:
            # Try to compute from positions
            returns = await self._compute_returns_from_positions(portfolio_data)

        if not returns:
            return {"error": "No historical return data available", "var_entries": []}

        # Sort returns ascending
        sorted_returns = sorted(returns)

        total_value = portfolio_data.get("total_value", 1_000_000)
        var_entries = []

        for horizon in time_horizons:
            scale = math.sqrt(horizon)
            for conf in confidence_levels:
                # Find the α-percentile
                alpha = 1 - conf
                index = int(len(sorted_returns) * alpha)
                index = max(0, min(index, len(sorted_returns) - 1))

                percentile_return = sorted_returns[index]

                # Scale by √horizon
                var_pct = abs(percentile_return) * scale
                var_value = total_value * var_pct

                var_entries.append({
                    "method": "historical",
                    "confidence_level": conf,
                    "time_horizon_days": horizon,
                    "var_value": round(var_value, 2),
                    "var_percentage": round(var_pct * 100, 4),
                    "portfolio_value": total_value,
                    "sample_size": len(sorted_returns),
                })

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        return {
            "method": "historical",
            "var_entries": var_entries,
            "calculation_time_ms": elapsed_ms,
            "sample_size": len(sorted_returns),
            "return_distribution": {
                "min": round(sorted_returns[0] * 100, 4) if sorted_returns else 0,
                "max": round(sorted_returns[-1] * 100, 4) if sorted_returns else 0,
                "mean": round(sum(sorted_returns) / len(sorted_returns) * 100, 4) if sorted_returns else 0,
                "skewness": await self._compute_skewness(sorted_returns) if sorted_returns else 0,
                "kurtosis": await self._compute_kurtosis(sorted_returns) if sorted_returns else 0,
            },
        }

    async def _compute_returns_from_positions(self, portfolio_data: dict[str, Any]) -> list[float]:
        """Attempt to compute historical returns from position data."""
        positions = portfolio_data.get("positions", [])
        if not positions:
            return []

        # If positions have embedded return history
        returns: list[float] = []
        for pos in positions:
            if isinstance(pos, dict) and "historical_returns" in pos:
                returns.extend(pos["historical_returns"])

        return returns[-self._window_days:] if returns else []

    @staticmethod
    async def _compute_skewness(data: list[float]) -> float:
        """Compute sample skewness."""
        n = len(data)
        if n < 3:
            return 0.0
        mean = sum(data) / n
        m2 = sum((x - mean) ** 2 for x in data) / n
        m3 = sum((x - mean) ** 3 for x in data) / n
        if m2 <= 0:
            return 0.0
        return m3 / (m2 ** 1.5)

    @staticmethod
    async def _compute_kurtosis(data: list[float]) -> float:
        """Compute sample excess kurtosis."""
        n = len(data)
        if n < 4:
            return 0.0
        mean = sum(data) / n
        m2 = sum((x - mean) ** 2 for x in data) / n
        m4 = sum((x - mean) ** 4 for x in data) / n
        if m2 <= 0:
            return 0.0
        return m4 / (m2 ** 2) - 3

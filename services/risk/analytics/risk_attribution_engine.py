"""
Risk Attribution Engine — Decompose portfolio risk into constituent sources.

Attributes portfolio return and risk to alpha, beta, factor exposures,
sector allocation, and residual/idiosyncratic components.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskAttributionEngine:
    """
    Risk attribution engine that decomposes portfolio performance.

    Attributes returns to:
    - Alpha (manager skill / security selection)
    - Beta (market exposure)
    - Factor exposures (momentum, value, size, etc.)
    - Sector allocation effects
    - Residual / idiosyncratic risk

    Methodology::

        Total Return
            │
            ├── Market Return (Beta)
            ├── Sector Allocation
            ├── Factor Exposures
            ├── Selection (Alpha)
            └── Residual (Idiosyncratic)

    Usage::

        engine = RiskAttributionEngine()
        await engine.initialize()
        results = await engine.attribute_risk(portfolio_data)
    """

    # Factor definitions
    FACTORS = [
        "market",
        "size",
        "value",
        "momentum",
        "quality",
        "low_volatility",
        "growth",
        "sector",
        "currency",
        "residual",
    ]

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the attribution engine."""
        self._initialized = True

    async def attribute_risk(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """
        Decompose portfolio risk and return.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio data with returns, positions, factor loadings.

        Returns
        -------
        dict
            Attribution breakdown.
        """
        total_value = portfolio_data.get("total_value", 1_000_000)
        positions = portfolio_data.get("positions", [])
        returns = portfolio_data.get("returns", [])
        factor_exposures = portfolio_data.get("factor_exposures", {})

        # Total return
        total_return_pct = self._compute_total_return(returns)

        # Market beta attribution
        beta = factor_exposures.get("market", 1.0)
        market_return = factor_exposures.get("market_return", total_return_pct * 0.6)
        beta_contribution = beta * market_return

        # Factor attributions
        factor_attribution: dict[str, dict[str, float]] = {}
        for factor in self.FACTORS:
            if factor == "market":
                continue
            loading = factor_exposures.get(factor, 0.0)
            factor_return = factor_exposures.get(f"{factor}_return", 0.0)
            contribution = loading * factor_return
            factor_attribution[factor] = {
                "loading": loading,
                "factor_return": factor_return,
                "contribution_pct": contribution,
            }

        # Sector attribution
        sector_attribution = self._attribute_sectors(positions, total_value)

        # Alpha (selection + timing)
        factor_total = sum(f["contribution_pct"] for f in factor_attribution.values())
        alpha = total_return_pct - beta_contribution - factor_total

        # Residual risk
        residual = total_return_pct - beta_contribution - factor_total - alpha

        # Risk decomposition (variance-based)
        risk_decomp = self._decompose_risk(
            total_return_pct, beta_contribution, factor_attribution, alpha
        )

        # Concentration
        concentration = self._compute_concentration(positions, total_value)

        return {
            "total_return_pct": round(total_return_pct, 4),
            "beta_attribution": {
                "beta": round(beta, 4),
                "market_return_pct": round(market_return, 4),
                "contribution_pct": round(beta_contribution, 4),
            },
            "factor_attribution": {
                k: {
                    "loading": round(v["loading"], 4),
                    "factor_return_pct": round(v["factor_return"], 4),
                    "contribution_pct": round(v["contribution_pct"], 4),
                }
                for k, v in factor_attribution.items()
            },
            "sector_attribution": sector_attribution,
            "alpha_pct": round(alpha, 4),
            "residual_pct": round(residual, 4),
            "risk_decomposition": risk_decomp,
            "concentration": concentration,
            "attribution_sum": round(
                beta_contribution + factor_total + alpha + residual, 4
            ),
        }

    def _compute_total_return(self, returns: list[float]) -> float:
        """Compute total period return from daily returns."""
        if not returns:
            return 0.0
        # Cumulative return
        total = 1.0
        for r in returns:
            total *= (1 + r)
        return (total - 1) * 100  # percentage

    def _attribute_sectors(
        self, positions: list[dict], total_value: float
    ) -> dict[str, Any]:
        """Attribute returns to sector allocation."""
        sectors: dict[str, float] = {}

        for pos in positions:
            if not isinstance(pos, dict):
                continue
            sector = pos.get("sector", "unknown")
            weight = pos.get("market_value", 0) / total_value if total_value > 0 else 0
            sector_return = pos.get("sector_return_pct", 0.0)
            contribution = weight * sector_return

            if sector not in sectors:
                sectors[sector] = 0.0
            sectors[sector] += contribution

        return {
            k: {
                "weight_pct": round(
                    sum(
                        p.get("market_value", 0) / total_value
                        for p in positions
                        if isinstance(p, dict) and p.get("sector") == k
                    ) * 100 if total_value > 0 else 0,
                    2,
                ),
                "contribution_pct": round(v, 4),
            }
            for k, v in sorted(sectors.items(), key=lambda x: abs(x[1]), reverse=True)
        }

    def _decompose_risk(
        self,
        total_return: float,
        beta_contribution: float,
        factor_attribution: dict[str, dict[str, float]],
        alpha: float,
    ) -> dict[str, Any]:
        """Variance-based risk decomposition."""
        import math

        # Simplified: proportional to absolute contributions
        total_abs = (
            abs(beta_contribution)
            + sum(abs(f["contribution_pct"]) for f in factor_attribution.values())
            + abs(alpha)
        )

        if total_abs == 0:
            return {"market_pct": 0, "factor_pct": 0, "alpha_pct": 0, "diversification_ratio": 1.0}

        return {
            "market_pct": round(abs(beta_contribution) / total_abs * 100, 1),
            "factor_pct": round(
                sum(abs(f["contribution_pct"]) for f in factor_attribution.values())
                / total_abs * 100,
                1,
            ),
            "alpha_pct": round(abs(alpha) / total_abs * 100, 1),
            "diversification_ratio": round(total_abs / (abs(beta_contribution) + 0.001), 2),
        }

    def _compute_concentration(
        self, positions: list[dict], total_value: float
    ) -> dict[str, Any]:
        """Compute concentration metrics."""
        if not positions or total_value <= 0:
            return {"hhi": 0, "top5_pct": 0, "effective_n": 0}

        weights = []
        for pos in positions:
            if isinstance(pos, dict):
                w = abs(pos.get("market_value", 0)) / total_value
                weights.append(w)

        sorted_w = sorted(weights, reverse=True)
        hhi = sum(w ** 2 for w in weights) * 10000  # scale to 0-10000
        top5_pct = sum(sorted_w[:5]) * 100

        # Effective number of positions
        effective_n = 1.0 / sum(w ** 2 for w in weights) if sum(w ** 2 for w in weights) > 0 else 0

        return {
            "hhi": round(hhi, 2),
            "top5_concentration_pct": round(top5_pct, 1),
            "effective_n": round(effective_n, 1),
            "total_positions": len(weights),
        }

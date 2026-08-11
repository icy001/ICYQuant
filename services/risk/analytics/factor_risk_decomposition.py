"""
Factor Risk Decomposition — Multi-factor risk decomposition engine.

Decomposes portfolio risk into systematic factor exposures:
Market, Sector, Momentum, Value, Growth, Quality, Size, Low Volatility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    """A single factor exposure measurement."""
    factor: str
    loading: float
    contribution_to_risk_pct: float
    contribution_to_return_pct: float
    marginal_risk_pct: float
    t_stat: float
    metadata: dict[str, Any] = field(default_factory=dict)


class FactorRiskDecomposition:
    """
    Multi-factor risk decomposition engine.

    Decomposes portfolio risk across standard risk factors::

        Total Risk
            │
            ├── Market (Systematic)
            ├── Sector
            ├── Momentum
            ├── Value
            ├── Growth
            ├── Quality
            ├── Size
            ├── Low Volatility
            └── Specific (Idiosyncratic)

    Usage::

        decomp = FactorRiskDecomposition()
        await decomp.initialize()
        results = await decomp.decompose(portfolio_data)
    """

    # Standard risk factors
    STANDARD_FACTORS = [
        "market",
        "sector",
        "momentum",
        "value",
        "growth",
        "quality",
        "size",
        "low_volatility",
        "dividend_yield",
        "profitability",
    ]

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the factor decomposition engine."""
        self._initialized = True

    async def decompose(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """
        Decompose portfolio risk by factors.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio with positions, returns, and factor loadings.

        Returns
        -------
        dict
            Factor-level risk decomposition.
        """
        total_value = portfolio_data.get("total_value", 1_000_000)
        positions = portfolio_data.get("positions", [])
        returns = portfolio_data.get("returns", [])
        factor_data = portfolio_data.get("factor_exposures", {})

        # Compute total risk (annualized volatility)
        total_risk = self._compute_total_risk(returns)

        # Factor exposures
        exposures: list[FactorExposure] = []
        for factor in self.STANDARD_FACTORS:
            loading = factor_data.get(factor, 0.0)
            factor_return = factor_data.get(f"{factor}_return", 0.0)
            factor_vol = factor_data.get(f"{factor}_volatility", 0.05)

            # Contribution to risk
            contribution_to_risk = abs(loading) * factor_vol
            contribution_to_return = loading * factor_return
            marginal_risk = loading * factor_vol ** 2

            # T-statistic for significance
            t_stat = loading / 0.05 if loading != 0 else 0.0

            exposures.append(FactorExposure(
                factor=factor,
                loading=round(loading, 4),
                contribution_to_risk_pct=round(contribution_to_risk * 100, 4),
                contribution_to_return_pct=round(contribution_to_return * 100, 4),
                marginal_risk_pct=round(marginal_risk * 100, 4),
                t_stat=round(t_stat, 2),
            ))

        # Total systematic risk
        systematic_risk = sum(e.contribution_to_risk_pct for e in exposures)

        # Specific (idiosyncratic) risk
        specific_risk = max(0, total_risk * 100 - systematic_risk)

        # Risk ratios
        total_risk_pct = total_risk * 100
        systematic_ratio = systematic_risk / total_risk_pct if total_risk_pct > 0 else 0
        specific_ratio = specific_risk / total_risk_pct if total_risk_pct > 0 else 0

        # Concentration
        risk_contributions = {e.factor: e.contribution_to_risk_pct for e in exposures}
        concentration = self._compute_risk_concentration(risk_contributions)

        return {
            "total_risk_annualized_pct": round(total_risk_pct, 2),
            "systematic_risk_pct": round(systematic_risk, 2),
            "specific_risk_pct": round(specific_risk, 2),
            "systematic_ratio": round(systematic_ratio, 2),
            "specific_ratio": round(specific_ratio, 2),
            "factor_exposures": [
                {
                    "factor": e.factor,
                    "loading": e.loading,
                    "contribution_to_risk_pct": e.contribution_to_risk_pct,
                    "contribution_to_return_pct": e.contribution_to_return_pct,
                    "marginal_risk_pct": e.marginal_risk_pct,
                    "t_stat": e.t_stat,
                }
                for e in sorted(exposures, key=lambda x: abs(x.contribution_to_risk_pct), reverse=True)
            ],
            "risk_concentration": concentration,
            "top_contributors": self._get_top_contributors(exposures, 3),
        }

    def _compute_total_risk(self, returns: list[float]) -> float:
        """Compute annualized volatility from daily returns."""
        import math

        if not returns or len(returns) < 2:
            return 0.20  # default

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        annual_vol = daily_vol * math.sqrt(252)

        return annual_vol

    def _compute_risk_concentration(
        self, contributions: dict[str, float]
    ) -> dict[str, Any]:
        """Compute risk concentration metrics."""
        total = sum(contributions.values())
        if total <= 0:
            return {"hhi": 0, "effective_n": 0}

        weights = {k: v / total for k, v in contributions.items()}
        hhi = sum(w ** 2 for w in weights.values()) * 10000
        effective_n = 1.0 / sum(w ** 2 for w in weights.values()) if sum(w ** 2 for w in weights.values()) > 0 else 0

        return {
            "hhi": round(hhi, 2),
            "effective_n_factors": round(effective_n, 1),
        }

    def _get_top_contributors(
        self, exposures: list[FactorExposure], n: int
    ) -> list[dict[str, Any]]:
        """Get top N risk contributors."""
        sorted_exp = sorted(
            exposures,
            key=lambda e: abs(e.contribution_to_risk_pct),
            reverse=True,
        )
        return [
            {"factor": e.factor, "contribution_pct": e.contribution_to_risk_pct}
            for e in sorted_exp[:n]
        ]

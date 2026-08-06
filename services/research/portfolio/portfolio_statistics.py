"""Portfolio Statistics — comprehensive statistical analysis of portfolios.

Computes portfolio-level statistics including:
* Concentration metrics (HHI, Gini, effective N)
* Diversification metrics
* Weight distribution analysis
* Risk contribution analysis
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PortfolioStats:
    """Comprehensive portfolio statistics."""

    # Concentration
    hhi: float = 0.0
    effective_n: float = 0.0
    gini_coefficient: float = 0.0
    top5_weight: float = 0.0
    top10_weight: float = 0.0

    # Weight distribution
    num_assets: int = 0
    num_zero_weight: int = 0
    min_weight: float = 0.0
    max_weight: float = 0.0
    mean_weight: float = 0.0
    std_weight: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    # Diversification
    diversification_ratio: float = 0.0
    concentration_ratio: float = 0.0

    # Risk contributions
    max_risk_contribution: float = 0.0
    max_rc_asset: str = ""
    risk_contribution_hhi: float = 0.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concentration": {
                "hhi": self.hhi,
                "effective_n": self.effective_n,
                "gini_coefficient": self.gini_coefficient,
                "top5_weight": self.top5_weight,
                "top10_weight": self.top10_weight,
            },
            "weight_distribution": {
                "num_assets": self.num_assets,
                "num_zero_weight": self.num_zero_weight,
                "min_weight": self.min_weight,
                "max_weight": self.max_weight,
                "mean_weight": self.mean_weight,
                "std_weight": self.std_weight,
                "skewness": self.skewness,
                "kurtosis": self.kurtosis,
            },
            "diversification": {
                "diversification_ratio": self.diversification_ratio,
                "concentration_ratio": self.concentration_ratio,
            },
            "risk_contributions": {
                "max_rc": self.max_risk_contribution,
                "max_rc_asset": self.max_rc_asset,
                "rc_hhi": self.risk_contribution_hhi,
            },
            "metadata": self.metadata,
        }


class PortfolioStatistics:
    """Compute comprehensive portfolio statistics.

    Provides concentration, diversification, weight distribution,
    and risk contribution analysis for portfolio assessment.
    """

    def __init__(self) -> None:
        pass

    async def compute(
        self,
        weights: Dict[str, float],
        universe: Optional[List[str]] = None,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        **kwargs: Any,
    ) -> PortfolioStats:
        """Compute all portfolio statistics.

        Args:
            weights: Portfolio weights.
            universe: Asset universe list.
            cov_matrix: Covariance matrix for risk contributions.

        Returns:
            PortfolioStats with all computed statistics.
        """
        assets = list(weights.keys())
        n = len(assets)

        stats = PortfolioStats(
            num_assets=n,
            num_zero_weight=sum(1 for w in weights.values() if abs(w) < 1e-6),
        )

        if n == 0:
            return stats

        # Weight distribution
        stats = self._weight_distribution(stats, weights)

        # Concentration metrics
        stats = self._concentration_metrics(stats, weights)

        # Diversification metrics
        if cov_matrix:
            stats = self._diversification_metrics(stats, weights, cov_matrix)

        # Risk contributions
        if cov_matrix:
            stats = self._risk_contributions(stats, weights, cov_matrix)

        return stats

    def _weight_distribution(
        self, stats: PortfolioStats, weights: Dict[str, float]
    ) -> PortfolioStats:
        """Compute weight distribution statistics."""
        w_list = list(weights.values())
        n = len(w_list)

        stats.min_weight = min(w_list)
        stats.max_weight = max(w_list)
        stats.mean_weight = sum(w_list) / n

        variance = sum((w - stats.mean_weight) ** 2 for w in w_list) / n
        stats.std_weight = variance ** 0.5

        # Skewness
        if stats.std_weight > 0:
            stats.skewness = sum(
                ((w - stats.mean_weight) / stats.std_weight) ** 3
                for w in w_list
            ) / n

        # Kurtosis (excess)
        if stats.std_weight > 0:
            stats.kurtosis = sum(
                ((w - stats.mean_weight) / stats.std_weight) ** 4
                for w in w_list
            ) / n - 3.0

        return stats

    def _concentration_metrics(
        self, stats: PortfolioStats, weights: Dict[str, float]
    ) -> PortfolioStats:
        """Compute concentration metrics."""
        w_list = list(weights.values())

        # HHI (Herfindahl-Hirschman Index)
        stats.hhi = sum(w * w for w in w_list)

        # Effective N
        stats.effective_n = 1.0 / stats.hhi if stats.hhi > 0 else 0.0

        # Gini coefficient
        stats.gini_coefficient = self._compute_gini(w_list)

        # Top-N weights
        sorted_w = sorted(w_list, reverse=True)
        stats.top5_weight = sum(sorted_w[:5])
        stats.top10_weight = sum(sorted_w[:10])

        return stats

    def _compute_gini(self, values: List[float]) -> float:
        """Compute Gini coefficient."""
        n = len(values)
        if n == 0:
            return 0.0

        sorted_v = sorted(values)
        cumsum = 0.0
        for i, v in enumerate(sorted_v):
            cumsum += (i + 1) * v

        total = sum(sorted_v)
        if total == 0:
            return 0.0

        return (2 * cumsum) / (n * total) - (n + 1) / n

    def _diversification_metrics(
        self,
        stats: PortfolioStats,
        weights: Dict[str, float],
        cov_matrix: Dict[str, Dict[str, float]],
    ) -> PortfolioStats:
        """Compute diversification metrics."""
        assets = list(weights.keys())

        # Weighted average volatility
        weighted_vol = 0.0
        for asset in assets:
            vol = max(cov_matrix.get(asset, {}).get(asset, 0.0), 1e-10) ** 0.5
            weighted_vol += weights.get(asset, 0.0) * vol

        # Portfolio volatility
        port_var = 0.0
        for i in assets:
            for j in assets:
                port_var += (
                    weights.get(i, 0.0)
                    * weights.get(j, 0.0)
                    * cov_matrix.get(i, {}).get(j, 0.0)
                )
        port_vol = max(port_var, 0.0) ** 0.5

        # Diversification ratio
        stats.diversification_ratio = (
            weighted_vol / port_vol if port_vol > 0 else 0.0
        )

        # Concentration ratio
        stats.concentration_ratio = 1.0 - (
            1.0 / stats.diversification_ratio
            if stats.diversification_ratio > 0
            else 0.0
        )

        return stats

    def _risk_contributions(
        self,
        stats: PortfolioStats,
        weights: Dict[str, float],
        cov_matrix: Dict[str, Dict[str, float]],
    ) -> PortfolioStats:
        """Compute risk contribution analysis."""
        assets = list(weights.keys())

        # Portfolio variance
        port_var = 0.0
        for i in assets:
            for j in assets:
                port_var += (
                    weights.get(i, 0.0)
                    * weights.get(j, 0.0)
                    * cov_matrix.get(i, {}).get(j, 0.0)
                )

        # Marginal risk contributions
        risk_contributions: Dict[str, float] = {}
        for asset in assets:
            w = weights.get(asset, 0.0)
            marginal = 0.0
            for j in assets:
                marginal += w * cov_matrix.get(asset, {}).get(j, 0.0)
            risk_contributions[asset] = marginal / max(port_var, 1e-10)

        # Max risk contribution
        if risk_contributions:
            stats.max_rc_asset = max(
                risk_contributions, key=risk_contributions.get
            )
            stats.max_risk_contribution = risk_contributions[stats.max_rc_asset]

            # RC HHI
            stats.risk_contribution_hhi = sum(
                rc * rc for rc in risk_contributions.values()
            )

        return stats

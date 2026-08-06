"""Factor Risk Model — multi-factor risk decomposition and analysis.

Decomposes portfolio risk into systematic (factor) and idiosyncratic
components, with factor exposure analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .covariance_estimator import CovarianceEstimator

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    """Exposure to a single factor."""

    factor: str
    exposure: float
    contribution_to_risk: float = 0.0
    contribution_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "exposure": self.exposure,
            "contribution_to_risk": self.contribution_to_risk,
            "contribution_pct": self.contribution_pct,
        }


@dataclass
class FactorRiskReport:
    """Complete factor risk analysis report."""

    total_risk: float = 0.0
    systematic_risk: float = 0.0
    idiosyncratic_risk: float = 0.0
    factor_exposures: List[FactorExposure] = field(default_factory=list)
    factor_covariance: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )
    asset_exposures: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_risk": self.total_risk,
            "systematic_risk": self.systematic_risk,
            "idiosyncratic_risk": self.idiosyncratic_risk,
            "systematic_pct": (
                self.systematic_risk / self.total_risk
                if self.total_risk > 0
                else 0.0
            ),
            "factor_exposures": [f.to_dict() for f in self.factor_exposures],
            "num_factors": len(self.factor_exposures),
            "metadata": self.metadata,
        }


class FactorRiskModel:
    """Multi-factor risk decomposition and analysis.

    Computes factor exposures, systematic vs idiosyncratic risk
    decomposition, and factor-level risk attribution.
    """

    # Common factor definitions
    DEFAULT_FACTORS = [
        "market",
        "size",
        "value",
        "momentum",
        "quality",
        "volatility",
    ]

    def __init__(
        self,
        cov_estimator: Optional[CovarianceEstimator] = None,
    ) -> None:
        self._cov_estimator = cov_estimator or CovarianceEstimator()
        self._factors = list(self.DEFAULT_FACTORS)

    async def analyze(
        self,
        weights: Dict[str, float],
        asset_exposures: Optional[Dict[str, Dict[str, float]]] = None,
        factor_cov: Optional[Dict[str, Dict[str, float]]] = None,
        idiosyncratic_var: Optional[Dict[str, float]] = None,
    ) -> FactorRiskReport:
        """Analyze factor risk for a portfolio.

        Args:
            weights: Portfolio weights.
            asset_exposures: Asset-level factor exposures.
            factor_cov: Factor covariance matrix.
            idiosyncratic_var: Idiosyncratic variance per asset.

        Returns:
            FactorRiskReport with risk decomposition.
        """
        assets = list(weights.keys())

        # Generate synthetic factor exposures if none provided
        if asset_exposures is None:
            asset_exposures = self._synthetic_exposures(assets)

        if factor_cov is None:
            factor_cov = self._synthetic_factor_cov()

        if idiosyncratic_var is None:
            idiosyncratic_var = {a: 0.01 for a in assets}

        # Compute portfolio-level factor exposures
        portfolio_exposures: Dict[str, float] = {}
        for factor in self._factors:
            exposure = 0.0
            for asset in assets:
                asset_exp = asset_exposures.get(asset, {}).get(factor, 0.0)
                exposure += weights.get(asset, 0.0) * asset_exp
            portfolio_exposures[factor] = exposure

        # Compute systematic risk: exp^T * F_cov * exp
        systematic_risk = 0.0
        for f1 in self._factors:
            for f2 in self._factors:
                exp1 = portfolio_exposures[f1]
                exp2 = portfolio_exposures[f2]
                fcov = factor_cov.get(f1, {}).get(f2, 0.0)
                systematic_risk += exp1 * exp2 * fcov

        # Compute idiosyncratic risk: Σ w_i^2 * σ_i^2
        idiosyncratic_risk = 0.0
        for asset in assets:
            w = weights.get(asset, 0.0)
            idiosyncratic_risk += w * w * idiosyncratic_var.get(asset, 0.0)

        total_risk = systematic_risk + idiosyncratic_risk

        # Factor contribution to systematic risk
        factor_exposures: List[FactorExposure] = []
        for factor in self._factors:
            exp = portfolio_exposures[factor]
            # Marginal contribution
            contrib = 0.0
            for f2 in self._factors:
                contrib += exp * portfolio_exposures[f2] * factor_cov.get(
                    factor, {}
                ).get(f2, 0.0)

            factor_exposures.append(FactorExposure(
                factor=factor,
                exposure=exp,
                contribution_to_risk=contrib,
                contribution_pct=(
                    contrib / total_risk if total_risk > 0 else 0.0
                ),
            ))

        # Sort by contribution
        factor_exposures.sort(
            key=lambda x: abs(x.contribution_to_risk), reverse=True
        )

        return FactorRiskReport(
            total_risk=total_risk,
            systematic_risk=systematic_risk,
            idiosyncratic_risk=idiosyncratic_risk,
            factor_exposures=factor_exposures,
            factor_covariance=factor_cov,
            asset_exposures=asset_exposures,
        )

    def _synthetic_exposures(
        self, assets: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Generate synthetic factor exposures."""
        import random
        random.seed(42)

        exposures: Dict[str, Dict[str, float]] = {}
        for asset in assets:
            exposures[asset] = {}
            for factor in self._factors:
                if factor == "market":
                    exposures[asset][factor] = random.uniform(0.5, 1.5)
                else:
                    exposures[asset][factor] = random.uniform(-1.0, 1.0)
        return exposures

    def _synthetic_factor_cov(self) -> Dict[str, Dict[str, float]]:
        """Generate synthetic factor covariance."""
        import random
        random.seed(42)

        n = len(self._factors)
        cov: Dict[str, Dict[str, float]] = {
            f: {g: 0.0 for g in self._factors} for f in self._factors
        }

        for i, f1 in enumerate(self._factors):
            for j, f2 in enumerate(self._factors):
                if i == j:
                    cov[f1][f2] = random.uniform(0.01, 0.05)
                else:
                    cov[f1][f2] = random.uniform(-0.01, 0.01)

        return cov

    @property
    def factors(self) -> List[str]:
        return list(self._factors)

    def add_factor(self, factor: str) -> None:
        if factor not in self._factors:
            self._factors.append(factor)

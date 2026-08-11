"""FactorRiskEngine — factor-based risk decomposition and analysis.

Decomposes portfolio risk into systematic factor contributions,
enabling factor concentration monitoring and shock simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FactorExposure:
    """Factor exposure for a strategy or portfolio."""

    entity_id: str
    exposures: Dict[str, float] = field(default_factory=dict)
    total_exposure: float = 0.0
    normalized: bool = False


@dataclass
class FactorRiskResult:
    """Factor risk decomposition result."""

    entity_id: str
    total_risk: float = 0.0
    factor_risks: Dict[str, float] = field(default_factory=dict)
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    specific_risk: float = 0.0
    systematic_risk_ratio: float = 0.0
    concentration_warnings: List[str] = field(default_factory=list)


class FactorRiskEngine:
    """Factor-based risk decomposition engine.

    Decomposes portfolio/strategy risk into factor contributions
    and identifies concentration risks.

    Standard factors:
    - Growth, Value, Momentum, Size, Quality, LowVol
    - AI, Tech, Rates, USD, Volatility, etc.

    Usage::

        engine = FactorRiskEngine()
        result = engine.decompose(
            entity_id="portfolio_1",
            exposures={"Momentum": 1.4, "Growth": 1.7, "Rates": -0.3},
            factor_vols={"Momentum": 0.15, "Growth": 0.18, "Rates": 0.08},
            factor_corrs={("Momentum", "Growth"): 0.3},
        )
    """

    def __init__(self, concentration_threshold: float = 1.5):
        self._concentration_threshold = concentration_threshold

    def decompose(
        self,
        entity_id: str,
        exposures: Dict[str, float],
        factor_vols: Dict[str, float],
        factor_corrs: Optional[Dict[Tuple[str, str], float]] = None,
        specific_risk: float = 0.0,
    ) -> FactorRiskResult:
        """Decompose risk into factor contributions.

        Args:
            entity_id: strategy or portfolio id
            exposures: {factor_name: exposure_value}
            factor_vols: {factor_name: annual_volatility}
            factor_corrs: pairwise factor correlations
            specific_risk: idiosyncratic/specific risk
        """
        import math

        factors = sorted(set(exposures.keys()) & set(factor_vols.keys()))
        n = len(factors)

        if n == 0:
            return FactorRiskResult(entity_id=entity_id, specific_risk=specific_risk)

        # build covariance matrix
        cov = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    cov[i][j] = factor_vols[factors[i]] ** 2
                else:
                    corr = 0.0
                    if factor_corrs:
                        corr = factor_corrs.get((factors[i], factors[j]), 0.0)
                        if corr == 0.0:
                            corr = factor_corrs.get((factors[j], factors[i]), 0.0)
                    cov[i][j] = corr * factor_vols[factors[i]] * factor_vols[factors[j]]

        # factor risk = sqrt(Σ_i Σ_j exp_i * exp_j * cov_ij)
        total_systematic_var = 0.0
        factor_contribs: Dict[str, float] = {}
        factor_risks: Dict[str, float] = {}

        for i in range(n):
            contrib = 0.0
            for j in range(n):
                contrib += exposures[factors[i]] * exposures[factors[j]] * cov[i][j]
            factor_contribs[factors[i]] = contrib
            factor_risks[factors[i]] = math.sqrt(max(0.0, contrib))
            total_systematic_var += contrib

        total_systematic_risk = math.sqrt(max(0.0, total_systematic_var))
        total_risk = math.sqrt(total_systematic_var + specific_risk ** 2)
        systematic_ratio = total_systematic_risk / max(total_risk, 1e-9)

        # concentration warnings
        warnings = []
        for f, exp in exposures.items():
            if abs(exp) > self._concentration_threshold:
                warnings.append(f"Factor {f} exposure {exp:.2f} exceeds threshold {self._concentration_threshold}")

        return FactorRiskResult(
            entity_id=entity_id,
            total_risk=total_risk,
            factor_risks=factor_risks,
            factor_contributions=factor_contribs,
            specific_risk=specific_risk,
            systematic_risk_ratio=systematic_ratio,
            concentration_warnings=warnings,
        )

    def compute_marginal_factor_risk(
        self,
        exposures: Dict[str, float],
        factor_vols: Dict[str, float],
        factor_corrs: Optional[Dict[Tuple[str, str], float]] = None,
        target_factor: str = "",
    ) -> float:
        """Compute marginal risk contribution of a single factor."""
        result = self.decompose("_marginal", exposures, factor_vols, factor_corrs)
        if target_factor:
            return result.factor_risks.get(target_factor, 0.0)
        return result.total_risk

    def compute_factor_diversification(
        self,
        exposures: Dict[str, float],
        factor_vols: Dict[str, float],
    ) -> float:
        """Compute factor diversification ratio.

        Ratio = sum(individual factor risks) / total systematic risk.
        Higher ratio means better diversification.
        """
        import math
        result = self.decompose("_div", exposures, factor_vols)
        sum_individual = sum(result.factor_risks.values())
        if result.total_risk > 0:
            return sum_individual / result.total_risk
        return 1.0

"""FactorConcentration — monitor and manage factor concentration risk.

Ensures no single factor dominates the portfolio and triggers
rebalancing when concentration exceeds limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ConcentrationReport:
    """Factor concentration analysis report."""

    entity_id: str
    overall_hhi: float = 0.0
    max_single_exposure: float = 0.0
    max_single_factor: str = ""
    factors_over_limit: Dict[str, float] = field(default_factory=dict)
    concentration_ratio_top3: float = 0.0
    effective_n_factors: float = 0.0
    risk_concentration: float = 0.0
    warnings: List[str] = field(default_factory=list)
    needs_rebalance: bool = False


class FactorConcentrationMonitor:
    """Monitors factor concentration across strategy/portfolio/capital levels.

    Concentration metrics:
    - HHI: Herfindahl-Hirschman Index
    - Top-N ratio
    - Effective N (inverse HHI)
    - Risk concentration

    Usage::

        monitor = FactorConcentrationMonitor(max_single_factor=3.0)
        report = monitor.analyze("portfolio_1", {"Growth": 2.0, "Momentum": 1.5, "AI": 4.0})
        if report.needs_rebalance:
            print("WARNING: Factor concentration breach")
    """

    def __init__(
        self,
        max_single_factor: float = 3.0,
        max_factor_concentration_pct: float = 35.0,
        max_hhi: float = 0.3,
        max_top3_ratio: float = 0.70,
    ):
        self._max_single_factor = max_single_factor
        self._max_concentration_pct = max_factor_concentration_pct
        self._max_hhi = max_hhi
        self._max_top3_ratio = max_top3_ratio

    def analyze(
        self,
        entity_id: str,
        exposures: Dict[str, float],
        factor_risks: Optional[Dict[str, float]] = None,
        total_risk: float = 0.0,
    ) -> ConcentrationReport:
        """Analyze factor concentration.

        Args:
            entity_id: strategy or portfolio id
            exposures: {factor_name: exposure_value}
            factor_risks: optional per-factor risk contributions
            total_risk: optional total risk
        """
        if not exposures:
            return ConcentrationReport(entity_id=entity_id)

        n = len(exposures)

        # total gross exposure
        total_gross = sum(abs(v) for v in exposures.values())

        # HHI
        hhi = 0.0
        if total_gross > 0:
            hhi = sum((abs(v) / total_gross) ** 2 for v in exposures.values())

        # effective N factors
        effective_n = 1.0 / max(hhi, 1e-9)

        # max single exposure
        max_factor = max(exposures.items(), key=lambda x: abs(x[1]))
        max_single = abs(max_factor[1])

        # top-3 ratio
        sorted_exposures = sorted(exposures.items(), key=lambda x: abs(x[1]), reverse=True)
        top3_sum = sum(abs(v) for _, v in sorted_exposures[:3])
        top3_ratio = top3_sum / max(total_gross, 1e-9)

        # factors over limit
        over_limit: Dict[str, float] = {}
        for f, v in exposures.items():
            if abs(v) > self._max_single_factor:
                over_limit[f] = abs(v)

        # risk concentration
        risk_conc = 0.0
        if factor_risks and total_risk > 0:
            risk_conc = sum(factor_risks.values()) / total_risk

        # warnings and rebalance
        warnings = []
        needs_rebalance = False

        if over_limit:
            needs_rebalance = True
            for f, v in over_limit.items():
                warnings.append(f"Factor {f} exposure {v:.2f} exceeds limit {self._max_single_factor}")

        if hhi > self._max_hhi:
            needs_rebalance = True
            warnings.append(f"HHI {hhi:.3f} exceeds limit {self._max_hhi}")

        if top3_ratio > self._max_top3_ratio:
            needs_rebalance = True
            warnings.append(f"Top-3 concentration {top3_ratio:.1%} exceeds {self._max_top3_ratio:.1%}")

        return ConcentrationReport(
            entity_id=entity_id,
            overall_hhi=hhi,
            max_single_exposure=max_single,
            max_single_factor=max_factor[0],
            factors_over_limit=over_limit,
            concentration_ratio_top3=top3_ratio,
            effective_n_factors=effective_n,
            risk_concentration=risk_conc,
            warnings=warnings,
            needs_rebalance=needs_rebalance,
        )

    def suggest_reduction(
        self,
        exposures: Dict[str, float],
        target_hhi: float = 0.20,
    ) -> Dict[str, float]:
        """Suggest exposure reductions to achieve target concentration."""
        report = self.analyze("_suggest", exposures)
        if not report.needs_rebalance:
            return {}

        suggestions: Dict[str, float] = {}
        total_gross = sum(abs(v) for v in exposures.values())

        for factor, over_exposure in report.factors_over_limit.items():
            target = self._max_single_factor
            if total_gross > 0:
                reduction = over_exposure - target
                suggestions[factor] = reduction / total_gross * 100

        return suggestions

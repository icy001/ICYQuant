"""RiskAggregationEngine — multi-level risk aggregation framework.

Aggregates risk from Strategy → Portfolio → Account → Capital Pool,
accounting for correlation, volatility scaling, and tail dependence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class AggregationLevel(Enum):
    STRATEGY = auto()
    PORTFOLIO = auto()
    ACCOUNT = auto()
    CAPITAL_POOL = auto()


@dataclass
class RiskComponent:
    """A single risk component (e.g., VaR, ES, drawdown contribution)."""

    name: str
    value: float
    weight: float = 1.0
    level: AggregationLevel = AggregationLevel.STRATEGY
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedRisk:
    """Result of risk aggregation at one level."""

    level: AggregationLevel
    total_risk: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_contribution: float = 0.0
    factor_risk: float = 0.0
    correlation_risk: float = 0.0
    tail_risk: float = 0.0
    marginal_risks: Dict[str, float] = field(default_factory=dict)
    components: List[RiskComponent] = field(default_factory=list)
    diversification_benefit: float = 0.0
    concentration_index: float = 0.0


class RiskAggregationEngine:
    """Multi-level risk aggregation with correlation and diversification awareness.

    Usage::

        engine = RiskAggregationEngine()
        result = engine.aggregate(
            strategy_risks,
            correlations,
            level=AggregationLevel.PORTFOLIO,
        )
    """

    def __init__(self):
        self._default_correlation: float = 0.3
        self._diversification_base: float = 0.85

    def aggregate(
        self,
        risk_components: Dict[str, float],
        correlations: Optional[Dict[Tuple[str, str], float]] = None,
        level: AggregationLevel = AggregationLevel.PORTFOLIO,
        weights: Optional[Dict[str, float]] = None,
    ) -> AggregatedRisk:
        """Aggregate risk components with correlation adjustment.

        Args:
            risk_components: {component_id: risk_value} mapping
            correlations: {(id_a, id_b): correlation} mapping
            level: aggregation target level
            weights: optional component weights (defaults to equal)
        """
        if not risk_components:
            return AggregatedRisk(level=level)

        n = len(risk_components)

        # equal weights if not specified
        if weights is None:
            weights = {k: 1.0 / n for k in risk_components}

        # compute weighted total
        weighted_total = sum(
            risk_components[k] * weights.get(k, 1.0 / n) for k in risk_components
        )

        # correlation adjustment
        corr_factor = self._compute_correlation_factor(
            risk_components, correlations
        )

        # diversification benefit (reduction from perfect correlation)
        diversification = self._diversification_base + 0.05 * min(n, 10) / 10
        adjusted_total = weighted_total * corr_factor * diversification

        # concentration index (HHI)
        total_weight = sum(weights.values())
        hhi = sum((w / max(total_weight, 1e-9)) ** 2 for w in weights.values())
        concentration = hhi

        return AggregatedRisk(
            level=level,
            total_risk=adjusted_total,
            var_95=adjusted_total * 0.95,
            var_99=adjusted_total * 1.2,
            expected_shortfall_95=adjusted_total * 1.3,
            expected_shortfall_99=adjusted_total * 1.6,
            diversification_benefit=1.0 - diversification,
            concentration_index=concentration,
            marginal_risks={
                k: risk_components[k] * corr_factor * diversification
                for k in risk_components
            },
        )

    def _compute_correlation_factor(
        self,
        components: Dict[str, float],
        correlations: Optional[Dict[Tuple[str, str], float]],
    ) -> float:
        """Compute the correlation amplification factor.

        When correlations are high, simple summation underestimates risk.
        This factor adjusts for that.
        """
        if not correlations or len(components) < 2:
            return 1.0

        keys = list(components.keys())
        avg_corr = 0.0
        count = 0
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                pair = (keys[i], keys[j])
                rev = (keys[j], keys[i])
                avg_corr += correlations.get(pair, correlations.get(rev, self._default_correlation))
                count += 1

        if count == 0:
            return 1.0

        avg_corr /= count
        n = len(components)

        # formula: sqrt(1 + (n-1)*corr) / sqrt(n) adjusts for correlation
        corr_factor = (1.0 + (n - 1) * avg_corr) ** 0.5 / (n ** 0.5)
        # clamp
        return max(1.0 / (n ** 0.5), min(corr_factor, 1.5))

    def compute_incremental_risk(
        self,
        current_risk: float,
        additional_risk: float,
        correlation: float,
    ) -> float:
        """Compute the incremental portfolio risk from adding a new component.

        incremental = sqrt(current^2 + additional^2 + 2*corr*current*additional)
        """
        return (
            current_risk ** 2
            + additional_risk ** 2
            + 2 * correlation * current_risk * additional_risk
        ) ** 0.5

    def compute_marginal_risk(
        self,
        incremental_portfolio_risk: float,
        incremental_capital: float,
    ) -> float:
        """Compute marginal risk = incremental risk / incremental capital."""
        if incremental_capital <= 0:
            return 0.0
        return incremental_portfolio_risk / incremental_capital

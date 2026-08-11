"""
Cross-Strategy Risk — Risk Interactions Between Strategies

Models how strategies' risks interact and amplify each other.
Risk is not additive — diversification can reduce, but correlation
can amplify the portfolio's total risk.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CrossStrategyRiskResult:
    pairwise_risks: Dict[str, Dict[str, float]] = field(default_factory=dict)
    diversification_benefit: float = 0.0
    risk_concentration: float = 0.0


class CrossStrategyRisk:
    """
    Computes risk interactions between strategy pairs.

    Diversification benefit = 1 - (portfolio_risk / sum_individual_risks)
    Risk concentration = highest pairwise risk contribution
    """

    def __init__(
        self,
        risk_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.risk_id = risk_id or f"csr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}

    def compute(
        self,
        strategy_risks: Dict[str, float],
        correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> CrossStrategyRiskResult:
        """
        Compute cross-strategy risk interactions.

        Args:
            strategy_risks: {strategy_id: risk_value}
            correlations: {s1: {s2: correlation}}
        """
        correlations = correlations or {}
        result = CrossStrategyRiskResult()
        ids = list(strategy_risks.keys())

        # Individual risk contribution
        individual_risk_total = sum(abs(v) for v in strategy_risks.values())

        # Pairwise risk
        for i in range(len(ids)):
            s1 = ids[i]
            result.pairwise_risks.setdefault(s1, {})
            for j in range(i + 1, len(ids)):
                s2 = ids[j]
                r1 = strategy_risks[s1]
                r2 = strategy_risks[s2]
                corr = correlations.get(s1, {}).get(s2, 0)
                pairwise = r1 * r2 * corr
                result.pairwise_risks[s1][s2] = pairwise
                result.pairwise_risks.setdefault(s2, {})[s1] = pairwise

        # Diversification benefit
        if individual_risk_total > 0:
            total_pairwise = sum(
                v for row in result.pairwise_risks.values()
                for v in row.values()
            )
            portfolio_risk = abs(individual_risk_total + total_pairwise) ** 0.5
            result.diversification_benefit = 1.0 - (portfolio_risk / individual_risk_total)
        else:
            result.diversification_benefit = 0.0

        # Risk concentration
        all_pairwise = [v for row in result.pairwise_risks.values() for v in row.values()]
        result.risk_concentration = max(all_pairwise) if all_pairwise else 0.0

        return result

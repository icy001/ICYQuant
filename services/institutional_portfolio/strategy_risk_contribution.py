"""
Strategy Risk Contribution — Risk Attribution to Individual Strategies

Computes how much each strategy contributes to total portfolio risk.
This is NOT capital allocation but RISK contribution.

Example:
    Strategy A → 12% of risk
    Strategy B → 28% of risk
    Strategy C → 7% of risk
    Strategy D → 43% of risk
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RiskContribution:
    strategy_id: str
    marginal_risk: float = 0.0       # d(Portfolio_Risk) / d(Strategy_Weight)
    component_risk: float = 0.0       # Weight × Marginal_Risk
    percentage_contribution: float = 0.0  # Component_Risk / Total_Risk


class StrategyRiskContribution:
    """
    Computes risk contribution of each strategy to the portfolio.

    Uses marginal risk contribution: how much does adding 1% more
    of this strategy increase portfolio risk?
    """

    def __init__(
        self,
        contrib_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.contrib_id = contrib_id or f"src-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._contributions: Dict[str, RiskContribution] = {}

    def compute(
        self,
        weights: Dict[str, float],
        covariance: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, RiskContribution]:
        """Compute risk contributions for each strategy."""
        covariance = covariance or {}
        self._contributions.clear()

        # Simplified: proportional to weight × risk
        for sid, weight in weights.items():
            risk = abs(weight) * 0.15  # Default vol assumption
            self._contributions[sid] = RiskContribution(
                strategy_id=sid,
                marginal_risk=risk,
                component_risk=risk * weight,
                percentage_contribution=0.0,  # Computed below
            )

        # Normalize to percentages
        total_comp = sum(c.component_risk for c in self._contributions.values())
        if total_comp > 0:
            for c in self._contributions.values():
                c.percentage_contribution = c.component_risk / total_comp

        return self._contributions

    def get_contribution(self, strategy_id: str) -> Optional[RiskContribution]:
        return self._contributions.get(strategy_id)

    def get_sorted_contributions(self) -> Dict[str, float]:
        """Return strategies sorted by risk contribution (descending)."""
        return {
            sid: c.percentage_contribution
            for sid, c in sorted(
                self._contributions.items(),
                key=lambda x: -x[1].percentage_contribution,
            )
        }

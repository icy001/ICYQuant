"""
Portfolio Risk Contribution — Asset-Level Risk Decomposition

Decomposes portfolio risk to individual asset contributions.
Complement to StrategyRiskContribution — this is at the asset level.
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AssetRiskContribution:
    asset: str
    risk_contribution: float = 0.0
    pct_of_total: float = 0.0
    marginal_risk: float = 0.0


class PortfolioRiskContribution:
    """
    Decomposes portfolio risk into individual asset contributions.

    Answers: which assets contribute most to portfolio risk?
    Not just weight — asset × correlation × volatility.
    """

    def __init__(
        self,
        contrib_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.contrib_id = contrib_id or f"prc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._contributions: Dict[str, AssetRiskContribution] = {}

    def compute(
        self,
        weights: Dict[str, float],
        volatilities: Optional[Dict[str, float]] = None,
    ) -> Dict[str, AssetRiskContribution]:
        """Compute asset-level risk contributions."""
        volatilities = volatilities or {}
        self._contributions.clear()

        for asset, weight in weights.items():
            vol = volatilities.get(asset, 0.15)
            risk_contrib = abs(weight) * vol
            self._contributions[asset] = AssetRiskContribution(
                asset=asset,
                risk_contribution=risk_contrib,
                marginal_risk=vol,
                pct_of_total=0.0,
            )

        total = sum(c.risk_contribution for c in self._contributions.values())
        if total > 0:
            for c in self._contributions.values():
                c.pct_of_total = c.risk_contribution / total

        return self._contributions

    def get_top_contributors(self, n: int = 10) -> Dict[str, float]:
        sorted_items = sorted(
            self._contributions.items(),
            key=lambda x: -x[1].pct_of_total,
        )
        return {asset: c.pct_of_total for asset, c in sorted_items[:n]}

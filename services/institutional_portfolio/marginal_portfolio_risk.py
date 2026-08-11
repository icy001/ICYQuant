"""
Marginal Portfolio Risk — Risk Impact of Adding/Removing Strategies

Computes the marginal risk contribution of adding a new strategy
or changing an existing strategy's allocation.

    Marginal Risk = Portfolio_Risk(new) - Portfolio_Risk(current)

If return doesn't justify the additional risk → reject/resize.
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MarginalRiskResult:
    strategy_id: str
    before_risk: float
    after_risk: float
    marginal_risk: float
    justified: bool = True
    reason: str = ""


class MarginalPortfolioRisk:
    """
    Computes risk impact of marginal capital allocation changes.

    Key question: "If I allocate more to Strategy X, how much
    additional portfolio risk does that create?"
    """

    def __init__(
        self,
        mpr_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.mpr_id = mpr_id or f"mpr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._risk_ratio_threshold = self.config.get("risk_ratio_threshold", 2.0)

    def evaluate(
        self,
        strategy_id: str,
        current_risk: float,
        additional_capital: float,
        incremental_return: float,
        current_weights: Optional[Dict[str, float]] = None,
    ) -> MarginalRiskResult:
        """
        Evaluate marginal risk of additional allocation.

        Marginal risk ≈ additional_capital_ratio × strategy_volatility × correlation_factor
        """
        risk_factor = 0.15  # Default vol
        marginal_risk = additional_capital * risk_factor
        new_risk = current_risk + marginal_risk

        # Justification: return / additional_risk >= threshold
        justified = False
        reason = ""
        if marginal_risk > 0:
            ratio = incremental_return / marginal_risk
            justified = ratio >= self._risk_ratio_threshold
            if justified:
                reason = f"Return/risk ratio {ratio:.2f} >= {self._risk_ratio_threshold}"
            else:
                reason = f"Return/risk ratio {ratio:.2f} < {self._risk_ratio_threshold} — reject"
        else:
            justified = True
            reason = "No additional risk"

        return MarginalRiskResult(
            strategy_id=strategy_id,
            before_risk=current_risk,
            after_risk=new_risk,
            marginal_risk=marginal_risk,
            justified=justified,
            reason=reason,
        )

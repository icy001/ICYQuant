"""
Marginal Risk Engine — computes the incremental risk of adding a position.

Answers: "If I add position X to my existing portfolio, how much does
         the overall portfolio risk change?"

Formula:
    Marginal VaR_i = d(VaR) / d(weight_i)
    Component VaR_i = weight_i * Marginal VaR_i

Use cases:
    - Pre-trade risk assessment
    - Position sizing decisions
    - Risk budget allocation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class MarginalRiskResult:
    """Result of marginal risk computation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    asset: str = ""
    existing_portfolio_var: float = 0.0
    portfolio_with_new_var: float = 0.0
    marginal_var: float = 0.0
    component_var: float = 0.0
    marginal_vol: float = 0.0
    correlation_with_portfolio: float = 0.0
    decision: str = "ALLOW"  # ALLOW, RESIZE, REJECT
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class MarginalRiskEngine:
    """
    Marginal risk computation engine.

    Core computations:
        1. Marginal VaR = β_i * VaR_portfolio
           where β_i = cov(asset_i, portfolio) / var(portfolio)

        2. Component VaR = weight_i * Marginal VaR_i

        3. Delta VaR = VaR(new_portfolio) - VaR(existing_portfolio)

    Decision thresholds:
        Marginal VaR < 20% of portfolio VaR → ALLOW
        Marginal VaR 20-35% → RESIZE recommendation
        Marginal VaR > 35% → REJECT
    """

    def __init__(
        self,
        allow_threshold: float = 0.20,
        reject_threshold: float = 0.35,
    ) -> None:
        self._allow_threshold = allow_threshold
        self._reject_threshold = reject_threshold

    async def compute(
        self,
        existing_positions: dict[str, float],
        new_asset: str,
        new_weight: float,
        portfolio_vol: float,
        new_asset_vol: float,
        correlation: float = 0.5,
    ) -> MarginalRiskResult:
        """
        Compute marginal risk of adding a new position.

        Args:
            existing_positions: Current portfolio {asset: weight}
            new_asset: Asset identifier
            new_weight: Proposed weight of new position
            portfolio_vol: Current portfolio volatility
            new_asset_vol: New asset's volatility
            correlation: Correlation between new asset and portfolio
        """
        result = MarginalRiskResult(
            asset=new_asset,
            existing_portfolio_var=portfolio_vol,
            correlation_with_portfolio=correlation,
        )

        # Marginal VaR
        beta = correlation * (new_asset_vol / max(portfolio_vol, 0.0001))
        result.marginal_var = beta * portfolio_vol
        result.component_var = new_weight * result.marginal_var
        result.marginal_vol = abs(beta) * portfolio_vol

        # New portfolio volatility
        existing_var = portfolio_vol ** 2
        new_var_contrib = (new_weight * new_asset_vol) ** 2
        cov_term = 2 * new_weight * existing_var * correlation
        new_portfolio_var = (existing_var + new_var_contrib + cov_term) ** 0.5
        result.portfolio_with_new_var = new_portfolio_var

        # Decision
        impact_ratio = (new_portfolio_var - portfolio_vol) / max(portfolio_vol, 0.0001)

        if impact_ratio <= self._allow_threshold:
            result.decision = "ALLOW"
            result.reason = f"Marginal impact {impact_ratio:.1%} within threshold"
        elif impact_ratio <= self._reject_threshold:
            result.decision = "RESIZE"
            result.reason = f"Marginal impact {impact_ratio:.1%} exceeds allow threshold"
        else:
            result.decision = "REJECT"
            result.reason = f"Marginal impact {impact_ratio:.1%} exceeds reject threshold"

        logger.debug(
            "Marginal risk: %s margin_var=%.4f impact=%.2f%% decision=%s",
            new_asset, result.marginal_var, impact_ratio * 100, result.decision,
        )
        return result

    async def compute_incremental_var(
        self,
        current_var: float,
        positions: dict[str, float],
        new_position: tuple[str, float],
        covariance: dict[str, dict[str, float]],
    ) -> float:
        """
        Compute VaR change from adding/removing a position using
        full covariance matrix.
        """
        asset, weight = new_position
        marginal_contrib = 0.0

        for other, w in positions.items():
            cov = covariance.get(asset, {}).get(other, 0)
            marginal_contrib += w * cov

        marginal_contrib += weight * covariance.get(asset, {}).get(asset, 0)

        ivar = (marginal_contrib / max(current_var, 0.0001)) * weight
        return ivar

    def beta_to_portfolio(
        self,
        asset_vol: float,
        portfolio_vol: float,
        correlation: float,
    ) -> float:
        """Compute beta of an asset to the portfolio."""
        if portfolio_vol <= 0:
            return 1.0
        return correlation * (asset_vol / portfolio_vol)

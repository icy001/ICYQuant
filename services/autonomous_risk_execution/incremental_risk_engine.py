"""
Incremental Risk Engine — computes risk change from position adjustments.

Unlike Marginal Risk (single addition), this engine handles:
    - Adding multiple positions simultaneously
    - Removing positions
    - Resizing existing positions
    - Rebalancing the portfolio
    - Impact of a full trade list
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class TradeImpact:
    """Risk impact of a proposed trade."""
    trade_id: str = ""
    action: str = ""  # BUY, SELL, CLOSE
    asset: str = ""
    quantity: float = 0.0
    var_before: float = 0.0
    var_after: float = 0.0
    var_delta: float = 0.0
    vol_delta: float = 0.0
    exposure_delta: float = 0.0


@dataclass
class IncrementalRiskResult:
    """Result of incremental risk analysis."""
    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_var_before: float = 0.0
    portfolio_var_after: float = 0.0
    var_delta_total: float = 0.0
    trade_impacts: list[TradeImpact] = field(default_factory=list)
    total_exposure_before: float = 0.0
    total_exposure_after: float = 0.0
    all_trades_acceptable: bool = True
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class IncrementalRiskEngine:
    """
    Computes risk changes from a set of trades.

    Workflow:
        1. Start with current portfolio risk profile
        2. Apply each trade sequentially
        3. Compute delta VaR, delta vol, delta exposure
        4. Check against risk limits
        5. Flag any trades that would breach limits
    """

    def __init__(self, max_incremental_var: float = 0.005) -> None:
        self._max_incremental_var = max_incremental_var

    async def analyze(
        self,
        current_portfolio: dict[str, float],
        trades: list[dict],
        cov_matrix: Optional[dict[str, dict[str, float]]] = None,
    ) -> IncrementalRiskResult:
        """
        Analyze incremental risk of a trade list.

        Args:
            current_portfolio: {asset: weight}
            trades: [{action, asset, quantity, ...}]
            cov_matrix: Optional covariance matrix
        """
        result = IncrementalRiskResult()

        # Current exposure
        gross = sum(abs(v) for v in current_portfolio.values())
        result.total_exposure_before = gross
        result.portfolio_var_before = gross * 0.02  # Simplified VaR

        # Simulate portfolio after trades
        simulated = dict(current_portfolio)
        net_var = result.portfolio_var_before

        for trade in trades:
            asset = trade.get("asset", "")
            action = trade.get("action", "").upper()
            quantity = trade.get("quantity", 0)

            impact = TradeImpact(
                trade_id=trade.get("id", ""),
                action=action, asset=asset, quantity=quantity,
                var_before=net_var,
            )

            before_weight = simulated.get(asset, 0)
            if action == "BUY":
                simulated[asset] = before_weight + quantity
            elif action == "SELL":
                simulated[asset] = before_weight - quantity
            elif action == "CLOSE":
                simulated[asset] = 0

            if simulated.get(asset, 0) == 0:
                simulated.pop(asset, None)

            # Recompute Var
            new_gross = sum(abs(v) for v in simulated.values())
            net_var = new_gross * 0.02
            impact.var_delta = net_var - impact.var_before
            impact.var_after = net_var
            impact.exposure_delta = new_gross - result.total_exposure_before

            # Check if this trade is acceptable
            if abs(impact.var_delta) > self._max_incremental_var:
                impact.var_delta = impact.var_delta  # flagged
                result.warnings.append(
                    f"Trade {impact.trade_id} ({asset}) delta VaR {impact.var_delta:.4f} "
                    f"exceeds limit {self._max_incremental_var:.4f}"
                )

            result.trade_impacts.append(impact)

        # Final portfolio state
        total_gross = sum(abs(v) for v in simulated.values())
        result.total_exposure_after = total_gross
        result.portfolio_var_after = net_var
        result.var_delta_total = net_var - result.portfolio_var_before
        result.all_trades_acceptable = len(result.warnings) == 0

        logger.info(
            "Incremental risk: %d trades, VaR %.4f→%.4f (Δ=%.4f), %d warnings",
            len(trades), result.portfolio_var_before, result.portfolio_var_after,
            result.var_delta_total, len(result.warnings),
        )
        return result

    async def check_trade(
        self, portfolio: dict[str, float], trade: dict[str, Any]
    ) -> bool:
        """Quick check if a single trade is risk-acceptable."""
        result = await self.analyze(portfolio, [trade])
        return result.all_trades_acceptable

    def estimate_impact(
        self, quantity: float, adv: float, volatility: float
    ) -> float:
        """Estimate market impact cost in bps."""
        if adv <= 0:
            return 0.0
        participation = abs(quantity) / adv
        return volatility * (participation ** 0.5) * 100  # bps

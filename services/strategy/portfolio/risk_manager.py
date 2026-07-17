"""
Portfolio Risk Manager.
"""

from __future__ import annotations

from decimal import Decimal

from .risk_result import RiskCheckResult
from .risk_limit import RiskLimit
from .portfolio_context import PortfolioContext


class PortfolioRiskManager:
    def check(
        self,
        exposure: Decimal,
        context: PortfolioContext,
        limit: RiskLimit,
    ) -> RiskCheckResult:
        new_exposure = context.current_exposure + exposure

        if new_exposure > limit.max_exposure:
            return RiskCheckResult(
                approved=False,
                reason="MAX_EXPOSURE_EXCEEDED",
            )

        if context.daily_loss > limit.max_daily_loss:
            return RiskCheckResult(
                approved=False,
                reason="DAILY_LOSS_LIMIT",
            )

        if context.max_drawdown > limit.max_drawdown:
            return RiskCheckResult(
                approved=False,
                reason="MAX_DRAWDOWN_LIMIT",
            )

        return RiskCheckResult(
            approved=True,
            reason="APPROVED",
        )
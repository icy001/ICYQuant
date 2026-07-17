"""
Portfolio analytics facade.
"""

from __future__ import annotations

from decimal import Decimal

from .analytics_snapshot import PortfolioAnalyticsSnapshot
from .performance_service import PerformanceService
from .pnl_service import PortfolioPnLService
from .valuation import PortfolioValuationService


class PortfolioAnalyticsService:
    def __init__(self):
        self.valuation = PortfolioValuationService()
        self.pnl = PortfolioPnLService()
        self.performance = PerformanceService()

    def snapshot(
        self,
        *,
        portfolio,
        cost_value: Decimal,
        realized_pnl: Decimal,
        beginning_value: Decimal,
        peak_value: Decimal,
        trough_value: Decimal,
        volatility: Decimal,
        sharpe_ratio: Decimal,
    ) -> PortfolioAnalyticsSnapshot:
        valuation = self.valuation.valuate(portfolio)

        pnl = self.pnl.calculate(
            cost_value=cost_value,
            market_value=valuation.market_value,
            realized_pnl=realized_pnl,
        )

        performance = self.performance.evaluate(
            beginning_value=beginning_value,
            ending_value=valuation.net_asset_value,
            peak_value=peak_value,
            trough_value=trough_value,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
        )

        return PortfolioAnalyticsSnapshot(
            valuation=valuation,
            pnl=pnl,
            performance=performance,
        )
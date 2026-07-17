"""
Portfolio valuation service.
"""

from __future__ import annotations

from .calculator import PortfolioCalculator
from .snapshot import PortfolioSnapshot


class PortfolioValuationService:
    def __init__(self):
        self.calculator = PortfolioCalculator()

    def valuate(
        self,
        portfolio,
    ) -> PortfolioSnapshot:
        market = self.calculator.market_value(portfolio)
        cash = self.calculator.cash_value(portfolio)
        total = market + cash

        return PortfolioSnapshot(
            market_value=market,
            cash_value=cash,
            gross_asset_value=total,
            net_asset_value=total,
        )
"""
Portfolio calculator.
"""

from __future__ import annotations

from decimal import Decimal

from .model import Portfolio


class PortfolioCalculator:
    def market_value(
        self,
        portfolio: Portfolio,
    ) -> Decimal:
        return sum(
            (
                position.market_value
                for position in portfolio.positions
            ),
            Decimal("0"),
        )

    def cash_value(
        self,
        portfolio: Portfolio,
    ) -> Decimal:
        return portfolio.cash.total
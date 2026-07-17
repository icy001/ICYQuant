"""
Portfolio PnL service.
"""

from __future__ import annotations

from decimal import Decimal

from .pnl import PnLCalculator
from .pnl_snapshot import PortfolioPnLSnapshot


class PortfolioPnLService:
    def __init__(self):
        self.calculator = PnLCalculator()

    def calculate(
        self,
        *,
        cost_value: Decimal,
        market_value: Decimal,
        realized_pnl: Decimal = Decimal("0"),
    ) -> PortfolioPnLSnapshot:
        unrealized = self.calculator.unrealized(
            cost_value,
            market_value,
        )

        realized = self.calculator.realized(
            realized_pnl,
        )

        total = self.calculator.total(
            unrealized,
            realized,
        )

        return PortfolioPnLSnapshot(
            unrealized_pnl=unrealized,
            realized_pnl=realized,
            total_pnl=total,
        )
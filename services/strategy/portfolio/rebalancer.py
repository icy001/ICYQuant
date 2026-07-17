"""
Dynamic portfolio rebalancer.
"""

from __future__ import annotations

from decimal import Decimal

from .rebalance_plan import RebalancePlan


class PortfolioRebalancer:
    def create_plan(
        self,
        symbol,
        drift,
        price,
        cost,
    ):
        if drift > 0:
            quantity = drift / price

            return RebalancePlan(
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                estimated_cost=cost,
            )

        return RebalancePlan(
            symbol=symbol,
            action="HOLD",
            quantity=Decimal("0"),
            estimated_cost=Decimal("0"),
        )
"""
Rebalance planner.
"""

from __future__ import annotations

from decimal import Decimal

from .allocation import Allocation


class RebalancePlanner:
    def trade_delta(
        self,
        allocation: Allocation,
        portfolio_value: Decimal,
    ) -> Decimal:
        target_value = (
            allocation.target_weight
            * portfolio_value
        )

        current_value = (
            allocation.current_weight
            * portfolio_value
        )

        return target_value - current_value
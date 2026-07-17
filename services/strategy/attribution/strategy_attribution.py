"""
Strategy level attribution.
"""

from __future__ import annotations

from decimal import Decimal


class StrategyAttribution:
    def calculate(
        self,
        trades,
    ):
        result = {}

        for trade in trades:
            strategy = trade.strategy_id

            result[strategy] = (
                result.get(strategy, Decimal("0"))
                +
                trade.pnl
            )

        return result
"""
Performance calculator.
"""

from __future__ import annotations

from decimal import Decimal


class PerformanceCalculator:
    def total_return(
        self,
        beginning_value: Decimal,
        ending_value: Decimal,
    ) -> Decimal:
        if beginning_value == 0:
            return Decimal("0")

        return (
            ending_value - beginning_value
        ) / beginning_value

    def cumulative_return(
        self,
        total_return: Decimal,
    ) -> Decimal:
        return total_return

    def max_drawdown(
        self,
        peak: Decimal,
        trough: Decimal,
    ) -> Decimal:
        if peak == 0:
            return Decimal("0")

        return (
            peak - trough
        ) / peak
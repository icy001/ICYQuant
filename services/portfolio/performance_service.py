"""
Performance service.
"""

from __future__ import annotations

from decimal import Decimal

from .performance import PerformanceCalculator
from .performance_snapshot import PerformanceSnapshot


class PerformanceService:
    def __init__(self):
        self.calculator = PerformanceCalculator()

    def evaluate(
        self,
        *,
        beginning_value: Decimal,
        ending_value: Decimal,
        peak_value: Decimal,
        trough_value: Decimal,
        volatility: Decimal,
        sharpe_ratio: Decimal,
    ) -> PerformanceSnapshot:
        total = self.calculator.total_return(
            beginning_value,
            ending_value,
        )

        cumulative = self.calculator.cumulative_return(
            total
        )

        drawdown = self.calculator.max_drawdown(
            peak_value,
            trough_value,
        )

        return PerformanceSnapshot(
            total_return=total,
            cumulative_return=cumulative,
            max_drawdown=drawdown,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
        )
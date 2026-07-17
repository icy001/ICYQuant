"""
Portfolio rebalance service.
"""

from __future__ import annotations

from decimal import Decimal

from .allocation import Allocation
from .drift import DriftCalculator


class RebalanceService:
    def __init__(self):
        self.calculator = DriftCalculator()

    def needs_rebalance(
        self,
        allocation: Allocation,
        threshold: Decimal,
    ) -> bool:
        drift = self.calculator.calculate(
            allocation
        )

        return drift >= threshold
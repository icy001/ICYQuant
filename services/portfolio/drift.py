"""
Allocation drift calculation.
"""

from __future__ import annotations

from decimal import Decimal

from .allocation import Allocation


class DriftCalculator:
    def calculate(
        self,
        allocation: Allocation,
    ) -> Decimal:
        return abs(
            allocation.current_weight
            -
            allocation.target_weight
        )
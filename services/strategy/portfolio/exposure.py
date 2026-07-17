"""
Exposure calculation.
"""

from __future__ import annotations

from decimal import Decimal


class ExposureCalculator:
    def calculate(
        self,
        quantity: Decimal,
        price: Decimal,
    ) -> Decimal:
        return quantity * price
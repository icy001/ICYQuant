"""
Factor exposure calculator.
"""

from __future__ import annotations

from decimal import Decimal


class FactorExposureCalculator:
    def calculate(
        self,
        positions,
        factor_map,
    ):
        exposure = {}

        for symbol, quantity in positions.items():
            factor = factor_map.get(symbol)

            if factor:
                exposure[factor] = (
                    exposure.get(factor, Decimal("0"))
                    +
                    quantity
                )

        return exposure
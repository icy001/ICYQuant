"""
Factor contribution.
"""

from __future__ import annotations

from decimal import Decimal


class FactorAttribution:
    def calculate(
        self,
        exposure,
        returns,
    ):
        result = {}

        for factor, value in exposure.items():
            result[factor] = (
                value
                *
                returns.get(factor, Decimal("0"))
            )

        return result
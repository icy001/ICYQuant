"""
Information coefficient calculation.
"""

from __future__ import annotations


class InformationCoefficient:
    def calculate(
        self,
        factor_values,
        future_returns,
    ):
        n = len(factor_values)

        if n == 0:
            return 0

        avg_factor = sum(factor_values) / n
        avg_return = sum(future_returns) / n

        numerator = sum(
            (x - avg_factor) * (y - avg_return)
            for x, y in zip(factor_values, future_returns)
        )

        return numerator
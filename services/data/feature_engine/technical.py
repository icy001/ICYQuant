"""
Technical indicator calculator.
"""

from __future__ import annotations


class TechnicalFeatureCalculator:
    def momentum(
        self,
        prices,
        period,
    ):
        if len(prices) <= period:
            return 0

        return prices[-1] / prices[-(period + 1)] - 1

    def volatility(
        self,
        returns,
    ):
        if not returns:
            return 0

        avg = sum(returns) / len(returns)
        variance = sum((x - avg) ** 2 for x in returns) / len(returns)

        return variance ** 0.5
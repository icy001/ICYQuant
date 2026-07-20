"""
Alpha Beta decomposition.
"""

from decimal import Decimal


class AlphaBetaCalculator:
    def calculate_alpha(
        self,
        portfolio_return,
        benchmark_return,
    ):
        return portfolio_return - benchmark_return

    def calculate_beta(
        self,
        covariance,
        market_variance,
    ):
        if market_variance == 0:
            return Decimal("0")
        return covariance / market_variance
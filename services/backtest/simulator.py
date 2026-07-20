"""
Portfolio simulator.
"""

from .equity import EquityCalculator


class PortfolioSimulator:
    def __init__(
        self,
        calculator: EquityCalculator,
    ):
        self.calculator = calculator

    def update(
        self,
        portfolio,
        market_value: float,
    ):
        portfolio.equity = self.calculator.calculate(
            portfolio.cash,
            market_value,
        )
        return portfolio
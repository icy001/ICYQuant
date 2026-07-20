"""
Portfolio service.
"""

from .simulator import PortfolioSimulator


class PortfolioService:
    def __init__(
        self,
        simulator: PortfolioSimulator,
    ):
        self.simulator = simulator

    def refresh(
        self,
        portfolio,
        market_value,
    ):
        return self.simulator.update(portfolio, market_value)
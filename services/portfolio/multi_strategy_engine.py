"""
Multi strategy portfolio engine.
"""


class MultiStrategyPortfolioEngine:
    def __init__(
        self,
        aggregator,
    ):
        self.aggregator = aggregator

    def calculate_value(
        self,
        strategies,
    ):
        return self.aggregator.aggregate(strategies)
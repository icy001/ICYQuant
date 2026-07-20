"""
Multi strategy service.
"""


class MultiStrategyService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def valuation(
        self,
        strategies,
    ):
        return self.engine.calculate_value(strategies)
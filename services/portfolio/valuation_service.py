"""
Valuation service.
"""


class ValuationService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def value(
        self,
        positions,
        prices,
        cash,
    ):
        return self.engine.calculate(positions, prices, cash)
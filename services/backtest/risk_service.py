"""
Risk service.
"""


class RiskService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def check(
        self,
        order,
        portfolio,
        rule,
    ):
        return self.engine.evaluate(order, portfolio, rule)
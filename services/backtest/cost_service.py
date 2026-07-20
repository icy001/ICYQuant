"""
Transaction cost service.
"""


class CostService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def apply(
        self,
        order,
        price,
    ):
        return self.engine.calculate(order, price)
"""
Risk budget service.
"""


class RiskBudgetService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def allocate(
        self,
        budget,
        amount,
    ):
        return self.engine.allocate(budget, amount)
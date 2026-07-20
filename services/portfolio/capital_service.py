"""
Capital service.
"""


class CapitalService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def allocate(
        self,
        pool,
        strategy_id,
        amount,
    ):
        return self.engine.allocate(pool, strategy_id, amount)
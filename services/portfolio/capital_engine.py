"""
Capital allocation engine.
"""


class CapitalAllocationEngine:
    def __init__(
        self,
        validator,
    ):
        self.validator = validator

    def allocate(
        self,
        pool,
        strategy_id,
        amount,
    ):
        if not self.validator.validate(pool, amount):
            raise ValueError("insufficient capital")

        pool.allocated_capital += amount

        return {
            "strategy_id": strategy_id,
            "allocated": amount,
        }
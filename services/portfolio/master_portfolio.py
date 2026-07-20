"""
Master portfolio container.
"""


class MasterPortfolio:
    def __init__(self):
        self.strategies = {}

    def add_strategy(
        self,
        strategy,
    ):
        self.strategies[strategy.strategy_id] = strategy

    def get_strategy(
        self,
        strategy_id,
    ):
        return self.strategies.get(strategy_id)
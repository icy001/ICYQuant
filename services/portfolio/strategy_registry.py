"""
Strategy registry.
"""


class StrategyRegistry:
    def __init__(self):
        self.strategies = {}

    def register(
        self,
        strategy,
    ):
        self.strategies[strategy.strategy_id] = strategy

    def list_all(self):
        return list(self.strategies.values())
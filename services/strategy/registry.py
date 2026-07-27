class StrategyRegistry:
    def __init__(self):
        self.strategies = {}

    def register(self, strategy):
        self.strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id):
        return self.strategies.get(strategy_id)
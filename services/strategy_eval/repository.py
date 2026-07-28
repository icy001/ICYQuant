class StrategyRepository:

    def __init__(self):

        self.data = {}

    def save(self, strategy):

        self.data[
            strategy.strategy_id
        ] = strategy

    def get(self, strategy_id):

        return self.data.get(strategy_id)

class StrategyService:
    def __init__(self, manager):
        self.manager = manager

    def run(self, strategy_id, market_data):
        return self.manager.execute(strategy_id, market_data)
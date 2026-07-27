class StrategyRuntimeManager:
    def __init__(self, registry, generator):
        self.registry = registry
        self.generator = generator

    def execute(self, strategy_id, market_data):
        strategy = self.registry.get(strategy_id)

        if not strategy:
            raise Exception("Strategy not found")

        return self.generator.generate(strategy, market_data)
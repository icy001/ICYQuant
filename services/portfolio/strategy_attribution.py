"""
Strategy performance attribution.
"""


class StrategyAttribution:
    def analyze(
        self,
        strategies,
    ):
        result = {}
        for strategy in strategies:
            result[strategy.strategy_id] = strategy.current_value
        return result
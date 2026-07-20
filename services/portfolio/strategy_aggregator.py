"""
Strategy exposure aggregator.
"""


class StrategyExposureAggregator:
    def aggregate(
        self,
        strategies,
    ):
        return sum(strategy.current_value for strategy in strategies)
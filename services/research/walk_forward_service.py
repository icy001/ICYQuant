"""
Walk-forward service.
"""

from .aggregator import WalkForwardAggregator


class WalkForwardService:
    def __init__(
        self,
        aggregator,
    ):
        self.aggregator = aggregator

    def summarize(
        self,
        results,
    ):
        return self.aggregator.aggregate(results)
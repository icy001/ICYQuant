"""
Portfolio position service.
"""


class PositionService:
    def __init__(
        self,
        aggregator,
    ):
        self.aggregator = aggregator

    def snapshot(
        self,
        positions,
        prices,
    ):
        return self.aggregator.aggregate(positions, prices)
"""
Risk aggregation service.
"""


class RiskAggregationService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def aggregate(self):

        return self.engine.aggregate()
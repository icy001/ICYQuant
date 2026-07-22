"""
Backtest result aggregator.
"""


class ResultAggregator:

    def __init__(self):

        self.results = []


    def collect(
        self,
        result,
    ):

        self.results.append(
            result
        )


    def aggregate(self):

        return self.results
"""
Risk metric aggregator.
"""


class RiskAggregator:

    def aggregate(
        self,
        metrics,
    ):

        result = {}

        for metric in metrics:

            result[
                metric.metric
            ] = metric.value

        return result
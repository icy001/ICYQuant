"""
Metrics aggregation.
"""


class MetricsAggregator:

    def aggregate(
        self,
        metrics,
    ):
        return {
            "total":
                len(metrics)
        }
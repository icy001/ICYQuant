class MetricsAggregator:

    def aggregate(
        self,
        metrics
    ):
        return sum(
            m.value
            for m in metrics
        )

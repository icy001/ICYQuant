class MetricsService:

    def __init__(
        self,
        repository,
        aggregator
    ):
        self.repository = repository
        self.aggregator = aggregator

    def record(
        self,
        metric
    ):
        self.repository.save(
            metric
        )

        return metric

    def summarize(self):
        return self.aggregator.aggregate(
            self.repository.all()
        )

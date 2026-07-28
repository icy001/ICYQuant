class MetricsRepository:

    def __init__(self):
        self.metrics = []

    def save(
        self,
        metric
    ):
        self.metrics.append(metric)

    def all(self):
        return self.metrics

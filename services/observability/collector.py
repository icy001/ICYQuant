class MetricCollector:

    def __init__(self):

        self.metrics = []

    def collect(self, metric):

        self.metrics.append(metric)

    def all(self):

        return self.metrics

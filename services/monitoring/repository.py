class MonitoringRepository:
    def __init__(self):
        self.metrics = {}

    def save(self, metric):
        self.metrics[metric.name] = metric

    def get(self, name):
        return self.metrics.get(name)
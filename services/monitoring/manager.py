class MonitoringManager:
    def __init__(self, repository, collector, checker):
        self.repository = repository
        self.collector = collector
        self.checker = checker

    def record(self, metric):
        result = self.collector.collect(metric)
        self.repository.save(result)
        return result

    def health(self, latency):
        return self.checker.check(latency)
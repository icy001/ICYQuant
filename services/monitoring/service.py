class MonitoringService:
    def __init__(self, manager):
        self.manager = manager

    def record_metric(self, metric):
        return self.manager.record(metric)

    def check_health(self, latency):
        return self.manager.health(latency)
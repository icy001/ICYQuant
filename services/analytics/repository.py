class AnalyticsRepository:
    def __init__(self):
        self.metrics = {}

    def save(self, key, value):
        self.metrics[key] = value

    def get(self, key):
        return self.metrics.get(key)
"""
Runtime metrics collector.
"""


class MetricsCollector:

    def __init__(self):
        self.metrics = {}

    def record(
        self,
        name,
        value,
    ):
        self.metrics[name] = value

    def snapshot(self):
        return self.metrics
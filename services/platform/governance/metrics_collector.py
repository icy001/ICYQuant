"""
Metrics collector.
"""


class MetricsCollector:

    def __init__(self):

        self.metrics = {}

    def record(
        self,
        name,
        value,
    ):

        self.metrics.setdefault(
            name,
            []
        ).append(value)

    def snapshot(self):

        return self.metrics
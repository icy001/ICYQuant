"""
Metric registry.
"""


class MetricRegistry:

    def __init__(self):
        self.metrics = {}

    def register(
        self,
        name,
        metric,
    ):
        self.metrics[name] = metric

    def get(
        self,
        name,
    ):
        return self.metrics.get(name)
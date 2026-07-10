"""
Metrics registry.

Central metric storage.
"""

from __future__ import annotations


class MetricsRegistry:
    def __init__(self):
        self.metrics = {}

    def register(
        self,
        metric,
    ):
        self.metrics[
            metric.name
        ] = metric

    def get(
        self,
        name,
    ):
        return self.metrics.get(
            name
        )

    def snapshot(
        self,
    ):
        return {
            name:
            metric.get()
            for name, metric
            in self.metrics.items()
        }
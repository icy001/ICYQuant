"""
Performance metrics service.
"""

from .summary import PerformanceSummary


class MetricsService:
    def __init__(
        self,
        summary,
    ):
        self.summary = summary

    def generate(
        self,
        metrics,
    ):
        return self.summary.build(metrics)
"""
Performance analytics service.
"""

from .performance import PerformanceAnalyzer


class AnalyticsService:
    def __init__(
        self,
        analyzer: PerformanceAnalyzer,
    ):
        self.analyzer = analyzer

    def evaluate(
        self,
        trades,
    ):
        return self.analyzer.analyze(trades)
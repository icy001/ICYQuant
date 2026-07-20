"""
Performance analyzer.
"""

from .statistics import TradeStatistics


class PerformanceAnalyzer:
    def __init__(
        self,
        statistics: TradeStatistics,
    ):
        self.statistics = statistics

    def analyze(
        self,
        trades,
    ):
        return self.statistics.summarize(trades)
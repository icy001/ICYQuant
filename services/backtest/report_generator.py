"""
Backtest report generator.
"""

from .backtest_report import BacktestReport


class ReportGenerator:

    def generate(
        self,
        summary,
        performance,
        trades,
    ):

        return BacktestReport(
            summary=summary,
            performance=performance,
            trades=trades,
        )
"""
Comparison service.
"""

from .report import ComparisonReport


class ComparisonService:
    def __init__(
        self,
        report,
    ):
        self.report = report

    def summarize(
        self,
        comparisons,
    ):
        return self.report.generate(comparisons)
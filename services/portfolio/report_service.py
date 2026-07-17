"""
Portfolio reporting service.
"""

from __future__ import annotations

from .report_builder import PortfolioReportBuilder


class PortfolioReportService:
    def __init__(self):
        self.builder = PortfolioReportBuilder()

    def generate(
        self,
        *,
        account_id: str,
        analytics,
    ):
        return self.builder.build(
            account_id=account_id,
            analytics=analytics,
        )
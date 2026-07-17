"""
Portfolio report builder.
"""

from __future__ import annotations

from .report import PortfolioReport
from .summary import PortfolioSummary


class PortfolioReportBuilder:
    def build(
        self,
        *,
        account_id: str,
        analytics,
    ) -> PortfolioReport:
        summary = PortfolioSummary(
            account_id=account_id,
            nav=analytics.valuation.net_asset_value,
            total_pnl=analytics.pnl.total_pnl,
            total_return=analytics.performance.total_return,
        )

        return PortfolioReport(
            summary=summary,
            analytics=analytics,
        )
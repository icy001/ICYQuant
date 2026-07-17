from decimal import Decimal

from services.portfolio import (
    PortfolioAnalyticsSnapshot,
    PortfolioReportService,
    PortfolioPnLSnapshot,
    PortfolioSnapshot,
    PerformanceSnapshot,
)


def test_generate_report():
    analytics = PortfolioAnalyticsSnapshot(
        valuation=PortfolioSnapshot(
            market_value=Decimal("10000"),
            cash_value=Decimal("2000"),
            gross_asset_value=Decimal("12000"),
            net_asset_value=Decimal("12000"),
        ),
        pnl=PortfolioPnLSnapshot(
            unrealized_pnl=Decimal("500"),
            realized_pnl=Decimal("300"),
            total_pnl=Decimal("800"),
        ),
        performance=PerformanceSnapshot(
            total_return=Decimal("0.08"),
            cumulative_return=Decimal("0.08"),
            max_drawdown=Decimal("0.03"),
            volatility=Decimal("0.12"),
            sharpe_ratio=Decimal("1.35"),
        ),
    )

    report = PortfolioReportService().generate(
        account_id="ACC001",
        analytics=analytics,
    )

    assert report.summary.account_id == "ACC001"
    assert report.summary.nav == Decimal("12000")
    assert report.summary.total_pnl == Decimal("800")


def test_report_analytics_access():
    analytics = PortfolioAnalyticsSnapshot(
        valuation=PortfolioSnapshot(
            market_value=Decimal("5000"),
            cash_value=Decimal("1000"),
            gross_asset_value=Decimal("6000"),
            net_asset_value=Decimal("6000"),
        ),
        pnl=PortfolioPnLSnapshot(
            unrealized_pnl=Decimal("200"),
            realized_pnl=Decimal("100"),
            total_pnl=Decimal("300"),
        ),
        performance=PerformanceSnapshot(
            total_return=Decimal("0.05"),
            cumulative_return=Decimal("0.05"),
            max_drawdown=Decimal("0.02"),
            volatility=Decimal("0.15"),
            sharpe_ratio=Decimal("1.0"),
        ),
    )

    report = PortfolioReportService().generate(
        account_id="ACC002",
        analytics=analytics,
    )

    assert report.analytics.valuation.market_value == Decimal("5000")
    assert report.analytics.pnl.unrealized_pnl == Decimal("200")
    assert report.analytics.performance.sharpe_ratio == Decimal("1.0")
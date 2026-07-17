from decimal import Decimal

from services.portfolio import (
    CashBalance,
    Portfolio,
    PortfolioAnalyticsService,
    PortfolioPosition,
    PortfolioStatus,
)


def test_analytics_snapshot():
    portfolio = Portfolio(
        account_id="ACC001",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("1000"),
            frozen=Decimal("0"),
        ),
        positions=[],
    )

    snapshot = PortfolioAnalyticsService().snapshot(
        portfolio=portfolio,
        cost_value=Decimal("0"),
        realized_pnl=Decimal("0"),
        beginning_value=Decimal("1000"),
        peak_value=Decimal("1000"),
        trough_value=Decimal("1000"),
        volatility=Decimal("0"),
        sharpe_ratio=Decimal("0"),
    )

    assert snapshot.valuation.cash_value == Decimal("1000")


def test_analytics_full_snapshot():
    portfolio = Portfolio(
        account_id="ACC002",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("5000"),
            frozen=Decimal("0"),
        ),
        positions=[
            PortfolioPosition(
                symbol="AAPL",
                quantity=Decimal("10"),
                market_value=Decimal("2500"),
            ),
        ],
    )

    snapshot = PortfolioAnalyticsService().snapshot(
        portfolio=portfolio,
        cost_value=Decimal("2000"),
        realized_pnl=Decimal("300"),
        beginning_value=Decimal("7000"),
        peak_value=Decimal("8000"),
        trough_value=Decimal("6500"),
        volatility=Decimal("0.20"),
        sharpe_ratio=Decimal("1.5"),
    )

    assert snapshot.valuation.market_value == Decimal("2500")
    assert snapshot.valuation.cash_value == Decimal("5000")
    assert snapshot.valuation.net_asset_value == Decimal("7500")
    assert snapshot.pnl.unrealized_pnl == Decimal("500")
    assert snapshot.pnl.realized_pnl == Decimal("300")
    assert snapshot.pnl.total_pnl == Decimal("800")
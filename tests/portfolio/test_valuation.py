from decimal import Decimal

from services.portfolio import (
    CashBalance,
    Portfolio,
    PortfolioPosition,
    PortfolioStatus,
    PortfolioValuationService,
)


def test_portfolio_valuation():
    portfolio = Portfolio(
        account_id="ACC001",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("1000"),
            frozen=Decimal("0"),
        ),
        positions=[
            PortfolioPosition(
                symbol="AAPL",
                quantity=Decimal("10"),
                market_value=Decimal("2500"),
            ),
            PortfolioPosition(
                symbol="MSFT",
                quantity=Decimal("5"),
                market_value=Decimal("1500"),
            ),
        ],
    )

    snapshot = PortfolioValuationService().valuate(portfolio)

    assert snapshot.market_value == Decimal("4000")
    assert snapshot.cash_value == Decimal("1000")
    assert snapshot.net_asset_value == Decimal("5000")


def test_empty_portfolio_valuation():
    portfolio = Portfolio(
        account_id="ACC002",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("500"),
            frozen=Decimal("0"),
        ),
        positions=[],
    )

    snapshot = PortfolioValuationService().valuate(portfolio)

    assert snapshot.market_value == Decimal("0")
    assert snapshot.cash_value == Decimal("500")
    assert snapshot.gross_asset_value == Decimal("500")
    assert snapshot.net_asset_value == Decimal("500")
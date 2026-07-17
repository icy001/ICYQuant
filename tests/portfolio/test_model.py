from decimal import Decimal

from services.portfolio import (
    CashBalance,
    Portfolio,
    PortfolioPosition,
    PortfolioStatus,
)


def test_portfolio_model():
    portfolio = Portfolio(
        account_id="ACC001",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("1000"),
            frozen=Decimal("200"),
        ),
        positions=[
            PortfolioPosition(
                symbol="AAPL",
                quantity=Decimal("10"),
                market_value=Decimal("2000"),
            )
        ],
    )

    assert portfolio.cash.total == Decimal("1200")
    assert len(portfolio.positions) == 1


def test_cash_balance():
    cash = CashBalance(
        currency="CNY",
        available=Decimal("5000"),
        frozen=Decimal("1000"),
    )
    assert cash.total == Decimal("6000")


def test_empty_portfolio():
    portfolio = Portfolio(
        account_id="ACC002",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("0"),
            frozen=Decimal("0"),
        ),
    )
    assert len(portfolio.positions) == 0
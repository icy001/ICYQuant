from decimal import Decimal

from services.portfolio import (
    CashBalance,
    Portfolio,
    PortfolioSerializer,
    PortfolioStatus,
)


def test_serializer():
    portfolio = Portfolio(
        account_id="ACC001",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("100"),
            frozen=Decimal("0"),
        ),
    )

    data = PortfolioSerializer().to_dict(portfolio)

    assert data["account_id"] == "ACC001"
    assert data["status"] == PortfolioStatus.ACTIVE


def test_serializer_with_positions():
    portfolio = Portfolio(
        account_id="ACC002",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("500"),
            frozen=Decimal("0"),
        ),
    )

    data = PortfolioSerializer().to_dict(portfolio)

    assert data["account_id"] == "ACC002"
    assert data["cash"]["currency"] == "USD"
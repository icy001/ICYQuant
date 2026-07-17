from decimal import Decimal

from services.portfolio import (
    PortfolioPnLService,
)


def test_portfolio_pnl():
    snapshot = PortfolioPnLService().calculate(
        cost_value=Decimal("10000"),
        market_value=Decimal("11250"),
        realized_pnl=Decimal("500"),
    )

    assert snapshot.unrealized_pnl == Decimal("1250")
    assert snapshot.realized_pnl == Decimal("500")
    assert snapshot.total_pnl == Decimal("1750")


def test_portfolio_pnl_loss():
    snapshot = PortfolioPnLService().calculate(
        cost_value=Decimal("10000"),
        market_value=Decimal("9500"),
        realized_pnl=Decimal("200"),
    )

    assert snapshot.unrealized_pnl == Decimal("-500")
    assert snapshot.total_pnl == Decimal("-300")


def test_portfolio_pnl_only_unrealized():
    snapshot = PortfolioPnLService().calculate(
        cost_value=Decimal("5000"),
        market_value=Decimal("5500"),
    )

    assert snapshot.unrealized_pnl == Decimal("500")
    assert snapshot.realized_pnl == Decimal("0")
    assert snapshot.total_pnl == Decimal("500")
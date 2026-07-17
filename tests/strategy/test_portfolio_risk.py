from decimal import Decimal

from services.strategy.portfolio import (
    PortfolioRiskManager,
    PortfolioContext,
    RiskLimit,
)


def test_exposure_limit():
    manager = PortfolioRiskManager()

    context = PortfolioContext(
        equity=Decimal("100000"),
        current_exposure=Decimal("40000"),
        daily_loss=Decimal("0"),
        max_drawdown=Decimal("0"),
    )

    limit = RiskLimit(
        max_exposure=Decimal("50000"),
        max_daily_loss=Decimal("5000"),
        max_drawdown=Decimal("10000"),
    )

    result = manager.check(
        exposure=Decimal("20000"),
        context=context,
        limit=limit,
    )

    assert result.approved is False
    assert result.reason == "MAX_EXPOSURE_EXCEEDED"


def test_risk_check_approved():
    manager = PortfolioRiskManager()

    context = PortfolioContext(
        equity=Decimal("100000"),
        current_exposure=Decimal("30000"),
        daily_loss=Decimal("1000"),
        max_drawdown=Decimal("5000"),
    )

    limit = RiskLimit(
        max_exposure=Decimal("50000"),
        max_daily_loss=Decimal("5000"),
        max_drawdown=Decimal("10000"),
    )

    result = manager.check(
        exposure=Decimal("10000"),
        context=context,
        limit=limit,
    )

    assert result.approved is True
    assert result.reason == "APPROVED"


def test_daily_loss_limit():
    manager = PortfolioRiskManager()

    context = PortfolioContext(
        equity=Decimal("100000"),
        current_exposure=Decimal("30000"),
        daily_loss=Decimal("6000"),
        max_drawdown=Decimal("5000"),
    )

    limit = RiskLimit(
        max_exposure=Decimal("50000"),
        max_daily_loss=Decimal("5000"),
        max_drawdown=Decimal("10000"),
    )

    result = manager.check(
        exposure=Decimal("10000"),
        context=context,
        limit=limit,
    )

    assert result.approved is False
    assert result.reason == "DAILY_LOSS_LIMIT"
from decimal import Decimal

from services.portfolio import (
    PerformanceService,
)


def test_performance():
    snapshot = PerformanceService().evaluate(
        beginning_value=Decimal("10000"),
        ending_value=Decimal("11000"),
        peak_value=Decimal("12000"),
        trough_value=Decimal("10000"),
        volatility=Decimal("0.18"),
        sharpe_ratio=Decimal("1.42"),
    )

    assert snapshot.total_return == Decimal("0.1")
    assert snapshot.max_drawdown == (
        Decimal("2000") / Decimal("12000")
    )


def test_performance_return_loss():
    snapshot = PerformanceService().evaluate(
        beginning_value=Decimal("10000"),
        ending_value=Decimal("9500"),
        peak_value=Decimal("10000"),
        trough_value=Decimal("9500"),
        volatility=Decimal("0.25"),
        sharpe_ratio=Decimal("-0.5"),
    )

    assert snapshot.total_return == Decimal("-0.05")


def test_performance_zero_beginning():
    snapshot = PerformanceService().evaluate(
        beginning_value=Decimal("0"),
        ending_value=Decimal("1000"),
        peak_value=Decimal("1000"),
        trough_value=Decimal("0"),
        volatility=Decimal("0"),
        sharpe_ratio=Decimal("0"),
    )

    assert snapshot.total_return == Decimal("0")
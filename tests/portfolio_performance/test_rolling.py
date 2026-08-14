"""Tests for the rolling performance analytics engine (Commit 35 Part 1.5)."""

from datetime import date, timedelta
from decimal import Decimal

from services.portfolio_performance import (
    RollingPerformanceCalculator,
)


def test_rolling_performance():

    calculator = RollingPerformanceCalculator()

    dates = [
        date(2026, 8, 1) + timedelta(days=index)
        for index in range(5)
    ]

    returns = [
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("-0.01"),
        Decimal("0.03"),
        Decimal("0.02"),
    ]

    results = calculator.calculate(
        dates=dates,
        returns=returns,
        window_size=3,
        annualization_factor=3,
    )

    assert len(results) == 3

    assert (
        results[0].as_of_date
        == date(2026, 8, 3)
    )

    assert (
        results[0].window_size
        == 3
    )


def test_rolling_return():

    calculator = RollingPerformanceCalculator()

    dates = [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
    ]

    returns = [
        Decimal("0.10"),
        Decimal("0.10"),
        Decimal("-0.10"),
    ]

    results = calculator.calculate(
        dates=dates,
        returns=returns,
        window_size=3,
        annualization_factor=3,
    )

    assert (
        results[0].total_return
        == Decimal("0.089")
    )


def test_rolling_requires_matching_lengths():

    calculator = RollingPerformanceCalculator()

    try:
        calculator.calculate(
            dates=[
                date(2026, 8, 1),
            ],
            returns=[
                Decimal("0.01"),
                Decimal("0.02"),
            ],
            window_size=2,
        )
    except ValueError as exc:
        assert (
            "same length"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_rolling_window_too_large():

    calculator = RollingPerformanceCalculator()

    results = calculator.calculate(
        dates=[
            date(2026, 8, 1),
            date(2026, 8, 2),
        ],
        returns=[
            Decimal("0.01"),
            Decimal("0.02"),
        ],
        window_size=3,
    )

    assert results == []

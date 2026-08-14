from decimal import Decimal

import pytest

from services.portfolio_performance import (
    RiskAdjustedPerformanceCalculator,
)


def test_volatility():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.volatility(
        [
            Decimal("0.01"),
            Decimal("-0.01"),
            Decimal("0.02"),
            Decimal("-0.02"),
        ],
        annualization_factor=1,
    )

    assert result > Decimal("0")


def test_downside_deviation():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.downside_deviation(
        [
            Decimal("0.01"),
            Decimal("-0.02"),
            Decimal("0.03"),
            Decimal("-0.01"),
        ],
        annualization_factor=1,
    )

    assert result > Decimal("0")


def test_sharpe_ratio():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.sharpe_ratio(
        [
            Decimal("0.01"),
            Decimal("0.02"),
            Decimal("0.01"),
            Decimal("0.03"),
        ],
        annualization_factor=1,
    )

    assert result > Decimal("0")


def test_sortino_ratio():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.sortino_ratio(
        [
            Decimal("0.01"),
            Decimal("-0.01"),
            Decimal("0.02"),
            Decimal("0.03"),
        ],
        annualization_factor=1,
    )

    assert result > Decimal("0")


def test_maximum_drawdown():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.maximum_drawdown(
        [
            Decimal("0.10"),
            Decimal("-0.20"),
            Decimal("0.05"),
        ]
    )

    assert result == Decimal("-0.2")


def test_calmar_ratio():
    calculator = RiskAdjustedPerformanceCalculator()

    result = calculator.calmar_ratio(
        [
            Decimal("0.02"),
            Decimal("-0.01"),
            Decimal("0.03"),
            Decimal("0.02"),
        ],
        annualization_factor=4,
    )

    assert result > Decimal("0")


def test_information_ratio():
    calculator = RiskAdjustedPerformanceCalculator()

    portfolio = [
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.01"),
        Decimal("0.04"),
    ]

    benchmark = [
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.01"),
        Decimal("0.02"),
    ]

    result = calculator.information_ratio(
        portfolio,
        benchmark,
        annualization_factor=1,
    )

    assert result > Decimal("0")


def test_beta():
    calculator = RiskAdjustedPerformanceCalculator()

    portfolio = [
        Decimal("0.02"),
        Decimal("0.04"),
        Decimal("0.06"),
        Decimal("0.08"),
    ]

    benchmark = [
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
    ]

    result = calculator.beta(
        portfolio,
        benchmark,
    )

    assert abs(
        result - Decimal("2")
    ) < Decimal("0.0000001")


def test_mismatched_benchmark_lengths():
    calculator = RiskAdjustedPerformanceCalculator()

    with pytest.raises(ValueError):
        calculator.information_ratio(
            [
                Decimal("0.01"),
            ],
            [
                Decimal("0.01"),
                Decimal("0.02"),
            ],
        )

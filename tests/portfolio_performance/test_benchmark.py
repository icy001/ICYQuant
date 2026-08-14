from datetime import date
from decimal import Decimal

from services.portfolio_performance import (
    BenchmarkObservation,
    BenchmarkPerformanceCalculator,
)


def test_benchmark_return_is_compounded():
    calculator = BenchmarkPerformanceCalculator()

    result = calculator.calculate_benchmark_return(
        [
            BenchmarkObservation(
                benchmark_id="SP500",
                trade_date=date(2026, 8, 13),
                return_pct=Decimal("0.05"),
            ),
            BenchmarkObservation(
                benchmark_id="SP500",
                trade_date=date(2026, 8, 14),
                return_pct=Decimal("0.10"),
            ),
        ]
    )

    assert result == Decimal("0.155")


def test_benchmark_observations_are_sorted():
    calculator = BenchmarkPerformanceCalculator()

    result = calculator.calculate_benchmark_return(
        [
            BenchmarkObservation(
                benchmark_id="SP500",
                trade_date=date(2026, 8, 14),
                return_pct=Decimal("0.10"),
            ),
            BenchmarkObservation(
                benchmark_id="SP500",
                trade_date=date(2026, 8, 13),
                return_pct=Decimal("0.05"),
            ),
        ]
    )

    assert result == Decimal("0.155")


def test_relative_performance():
    calculator = BenchmarkPerformanceCalculator()

    result = calculator.calculate_relative_performance(
        portfolio_return=Decimal("0.20"),
        benchmark_return=Decimal("0.15"),
    )

    assert result.portfolio_return == Decimal("0.20")
    assert result.benchmark_return == Decimal("0.15")
    assert result.active_return == Decimal("0.05")
    assert result.tracking_difference == Decimal("0.05")

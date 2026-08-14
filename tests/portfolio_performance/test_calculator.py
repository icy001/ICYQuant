from datetime import date
from decimal import Decimal

import pytest

from services.portfolio_performance import (
    BenchmarkObservation,
    PortfolioPerformanceCalculator,
    PortfolioPerformanceInput,
)


def test_calculate_basic_portfolio_pnl():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=date(2026, 8, 14),
            beginning_equity=Decimal("100000"),
            ending_equity=Decimal("105000"),
        )
    )

    assert result.pnl == Decimal("5000")
    assert result.return_pct == Decimal("0.05")


def test_external_cash_flow_is_excluded():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=date(2026, 8, 14),
            beginning_equity=Decimal("100000"),
            ending_equity=Decimal("115000"),
            external_cash_flow=Decimal("10000"),
        )
    )

    assert result.pnl == Decimal("5000")
    assert result.return_pct == Decimal("0.05")


def test_negative_external_cash_flow():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=date(2026, 8, 14),
            beginning_equity=Decimal("100000"),
            ending_equity=Decimal("95000"),
            external_cash_flow=Decimal("-10000"),
        )
    )

    assert result.pnl == Decimal("5000")
    assert result.return_pct == Decimal("0.05")


def test_pnl_component_reconciliation():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=date(2026, 8, 14),
            beginning_equity=Decimal("100000"),
            ending_equity=Decimal("105000"),
            trading_pnl=Decimal("4000"),
            financing_pnl=Decimal("500"),
            fee_pnl=Decimal("-100"),
            other_pnl=Decimal("600"),
        )
    )

    assert result.pnl == Decimal("5000")

    assert result.total_internal_pnl == Decimal("5000")

    assert result.reconciliation_residual == Decimal("0")


def test_non_zero_reconciliation_residual():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=date(2026, 8, 14),
            beginning_equity=Decimal("100000"),
            ending_equity=Decimal("105000"),
            trading_pnl=Decimal("4000"),
            financing_pnl=Decimal("500"),
        )
    )

    assert result.reconciliation_residual == Decimal("500")


def test_zero_beginning_equity_is_rejected():
    calculator = PortfolioPerformanceCalculator()

    with pytest.raises(ValueError):
        calculator.calculate(
            PortfolioPerformanceInput(
                portfolio_id="portfolio-001",
                trade_date=date(2026, 8, 14),
                beginning_equity=Decimal("0"),
                ending_equity=Decimal("1000"),
            )
        )


def test_negative_beginning_equity_is_rejected():
    calculator = PortfolioPerformanceCalculator()

    with pytest.raises(ValueError):
        calculator.calculate(
            PortfolioPerformanceInput(
                portfolio_id="portfolio-001",
                trade_date=date(2026, 8, 14),
                beginning_equity=Decimal("-1"),
                ending_equity=Decimal("1000"),
            )
        )


def build_record(
    trade_date: date,
    beginning: str,
    ending: str,
    cash_flow: str = "0",
):
    calculator = PortfolioPerformanceCalculator()

    return calculator.calculate(
        PortfolioPerformanceInput(
            portfolio_id="portfolio-001",
            trade_date=trade_date,
            beginning_equity=Decimal(beginning),
            ending_equity=Decimal(ending),
            external_cash_flow=Decimal(cash_flow),
        )
    )


def test_period_twr():
    calculator = PortfolioPerformanceCalculator()

    records = [
        build_record(
            date(2026, 8, 13),
            "100000",
            "105000",
        ),
        build_record(
            date(2026, 8, 14),
            "105000",
            "108150",
        ),
    ]

    report = calculator.calculate_period(
        records
    )

    assert report.twr == Decimal("0.0815")


def test_period_pnl():
    calculator = PortfolioPerformanceCalculator()

    records = [
        build_record(
            date(2026, 8, 13),
            "100000",
            "105000",
        ),
        build_record(
            date(2026, 8, 14),
            "105000",
            "108150",
        ),
    ]

    report = calculator.calculate_period(
        records
    )

    assert report.total_pnl == Decimal("8150")


def test_period_external_cash_flow():
    calculator = PortfolioPerformanceCalculator()

    records = [
        build_record(
            date(2026, 8, 13),
            "100000",
            "105000",
            "0",
        ),
        build_record(
            date(2026, 8, 14),
            "105000",
            "118150",
            "10000",
        ),
    ]

    report = calculator.calculate_period(
        records
    )

    assert report.total_external_cash_flow == Decimal("10000")

    # Day1 pnl = 105000 - 100000 - 0 = 5000
    # Day2 pnl = 118150 - 105000 - 10000 = 3150
    # total_pnl = sum of daily pnl = 8150
    assert report.total_pnl == Decimal("8150")


def test_benchmark_relative_performance():
    calculator = PortfolioPerformanceCalculator()

    portfolio_records = [
        calculator.calculate(
            PortfolioPerformanceInput(
                portfolio_id="portfolio-001",
                trade_date=date(2026, 8, 13),
                beginning_equity=Decimal("100000"),
                ending_equity=Decimal("105000"),
            )
        ),
        calculator.calculate(
            PortfolioPerformanceInput(
                portfolio_id="portfolio-001",
                trade_date=date(2026, 8, 14),
                beginning_equity=Decimal("105000"),
                ending_equity=Decimal("110250"),
            )
        ),
    ]

    benchmark = [
        BenchmarkObservation(
            benchmark_id="SP500",
            trade_date=date(2026, 8, 13),
            return_pct=Decimal("0.03"),
        ),
        BenchmarkObservation(
            benchmark_id="SP500",
            trade_date=date(2026, 8, 14),
            return_pct=Decimal("0.04"),
        ),
    ]

    result = calculator.calculate_benchmark_relative(
        portfolio_id="portfolio-001",
        benchmark_id="SP500",
        portfolio_records=portfolio_records,
        benchmark_observations=benchmark,
    )

    assert result.portfolio_return == Decimal("0.1025")
    assert result.benchmark_return == Decimal("0.0712")
    assert result.active_return == Decimal("0.0313")


def test_calculate_risk_metrics():
    calculator = PortfolioPerformanceCalculator()

    result = calculator.calculate_risk_metrics(
        portfolio_returns=[
            Decimal("0.01"),
            Decimal("-0.005"),
            Decimal("0.02"),
            Decimal("0.015"),
        ],
        benchmark_returns=[
            Decimal("0.008"),
            Decimal("-0.004"),
            Decimal("0.015"),
            Decimal("0.01"),
        ],
        annualization_factor=4,
    )

    assert result.volatility > Decimal("0")
    assert result.downside_deviation > Decimal("0")

    assert result.sharpe_ratio != Decimal("0")
    assert result.sortino_ratio != Decimal("0")

    assert result.maximum_drawdown <= Decimal("0")

    assert result.information_ratio > Decimal("0")

    assert result.beta > Decimal("0")


def test_calculator_rolling_performance():

    calculator = PortfolioPerformanceCalculator()

    dates = [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
    ]

    returns = [
        Decimal("0.01"),
        Decimal("-0.005"),
        Decimal("0.02"),
        Decimal("0.015"),
    ]

    results = (
        calculator.calculate_rolling_performance(
            dates=dates,
            returns=returns,
            window_size=3,
            annualization_factor=3,
        )
    )

    assert len(results) == 2

    assert (
        results[0].as_of_date
        == date(2026, 8, 3)
    )

    assert (
        results[1].as_of_date
        == date(2026, 8, 4)
    )

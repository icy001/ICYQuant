from datetime import date
from decimal import Decimal

from services.portfolio_performance import (
    BenchmarkObservation,
    PortfolioPerformanceService,
)


def test_service_calculation():
    service = PortfolioPerformanceService()

    result = service.calculate(
        portfolio_id="portfolio-001",
        trade_date=date(2026, 8, 14),
        beginning_equity="100000",
        ending_equity="108000",
        external_cash_flow="5000",
        trading_pnl="2500",
        financing_pnl="500",
        fee_pnl="-100",
        other_pnl="100",
    )

    assert result.portfolio_id == "portfolio-001"

    assert result.pnl == Decimal("3000")

    assert result.return_pct == Decimal("0.03")

    assert result.total_internal_pnl == Decimal("3000")

    assert result.reconciliation_residual == Decimal("0")


def test_service_period_performance():
    service = PortfolioPerformanceService()

    day_1 = service.calculate(
        portfolio_id="portfolio-001",
        trade_date=date(2026, 8, 13),
        beginning_equity="100000",
        ending_equity="105000",
    )

    day_2 = service.calculate(
        portfolio_id="portfolio-001",
        trade_date=date(2026, 8, 14),
        beginning_equity="105000",
        ending_equity="108150",
    )

    report = service.calculate_period(
        [day_1, day_2]
    )

    assert report.portfolio_id == "portfolio-001"
    assert report.observation_count == 2

    assert report.twr == Decimal("0.0815")


def test_service_benchmark_relative_performance():
    service = PortfolioPerformanceService()

    day_1 = service.calculate(
        portfolio_id="portfolio-001",
        trade_date=date(2026, 8, 13),
        beginning_equity="100000",
        ending_equity="105000",
    )

    day_2 = service.calculate(
        portfolio_id="portfolio-001",
        trade_date=date(2026, 8, 14),
        beginning_equity="105000",
        ending_equity="110250",
    )

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

    result = service.calculate_benchmark_relative(
        portfolio_id="portfolio-001",
        benchmark_id="SP500",
        portfolio_records=[day_1, day_2],
        benchmark_observations=benchmark,
    )

    assert result.active_return == Decimal("0.0313")


def test_service_risk_metrics():
    service = PortfolioPerformanceService()

    result = service.calculate_risk_metrics(
        portfolio_returns=[
            "0.01",
            "-0.005",
            "0.02",
            "0.015",
        ],
        benchmark_returns=[
            "0.008",
            "-0.004",
            "0.015",
            "0.01",
        ],
        annualization_factor=4,
    )

    assert result.volatility > Decimal("0")
    assert result.sharpe_ratio != Decimal("0")
    assert result.information_ratio > Decimal("0")


def test_service_rolling_performance():

    service = PortfolioPerformanceService()

    dates = [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
    ]

    returns = [
        "0.01",
        "-0.005",
        "0.02",
        "0.015",
    ]

    results = service.calculate_rolling_performance(
        dates=dates,
        returns=returns,
        window_size=3,
        annualization_factor=3,
    )

    assert len(results) == 2

    assert (
        results[0].total_return
        != Decimal("0")
    )

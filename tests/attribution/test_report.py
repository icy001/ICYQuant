from datetime import date
from decimal import Decimal

import pytest

from services.attribution import (
    AttributionEngine,
    AttributionInput,
    AttributionReportBuilder,
)


def build_result(
    trade_date: date,
    strategy_return: str,
    benchmark_return: str,
    trading: str = "0",
    financing: str = "0",
    fees: str = "0",
    other: str = "0",
    gross: str = "0",
    net: str = "0",
):
    engine = AttributionEngine()

    return engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=trade_date,
            strategy_return=Decimal(strategy_return),
            benchmark_return=Decimal(benchmark_return),
            trading_pnl=Decimal(trading),
            financing_pnl=Decimal(financing),
            fee_pnl=Decimal(fees),
            other_pnl=Decimal(other),
            gross_exposure=Decimal(gross),
            net_exposure=Decimal(net),
        )
    )


def test_period_return_is_compounded():
    builder = AttributionReportBuilder()

    records = [
        build_result(
            date(2026, 8, 13),
            "0.10",
            "0.05",
        ),
        build_result(
            date(2026, 8, 14),
            "0.20",
            "0.10",
        ),
    ]

    report = builder.build(records)

    assert report.strategy_return == Decimal("0.32")
    assert report.benchmark_return == Decimal("0.155")
    assert report.active_return == Decimal("0.165")


def test_contributions_are_aggregated():
    builder = AttributionReportBuilder()

    records = [
        build_result(
            date(2026, 8, 13),
            "0.05",
            "0.02",
            trading="0.02",
            financing="0.003",
            fees="-0.001",
            other="0.001",
        ),
        build_result(
            date(2026, 8, 14),
            "0.06",
            "0.02",
            trading="0.025",
            financing="0.002",
            fees="-0.001",
            other="0.001",
        ),
    ]

    report = builder.build(records)

    assert report.trading_contribution == Decimal("0.045")
    assert report.financing_contribution == Decimal("0.005")
    assert report.fee_contribution == Decimal("-0.002")
    assert report.other_contribution == Decimal("0.002")


def test_residual_reconciles_to_active_return():
    builder = AttributionReportBuilder()

    records = [
        build_result(
            date(2026, 8, 13),
            "0.05",
            "0.02",
            trading="0.02",
        ),
        build_result(
            date(2026, 8, 14),
            "0.06",
            "0.02",
            trading="0.025",
        ),
    ]

    report = builder.build(records)

    assert report.attribution_check == Decimal("0")


def test_dates_are_sorted_before_reporting():
    builder = AttributionReportBuilder()

    records = [
        build_result(
            date(2026, 8, 14),
            "0.02",
            "0.01",
        ),
        build_result(
            date(2026, 8, 13),
            "0.03",
            "0.01",
        ),
    ]

    report = builder.build(records)

    assert report.start_date == date(2026, 8, 13)
    assert report.end_date == date(2026, 8, 14)


def test_exposure_is_averaged():
    builder = AttributionReportBuilder()

    records = [
        build_result(
            date(2026, 8, 13),
            "0.01",
            "0.00",
            gross="1.0",
            net="0.5",
        ),
        build_result(
            date(2026, 8, 14),
            "0.01",
            "0.00",
            gross="1.4",
            net="0.7",
        ),
    ]

    report = builder.build(records)

    assert report.gross_exposure == Decimal("1.2")
    assert report.net_exposure == Decimal("0.6")


def test_empty_records_are_rejected():
    builder = AttributionReportBuilder()

    with pytest.raises(ValueError):
        builder.build([])


def test_multiple_strategies_are_rejected():
    engine = AttributionEngine()

    first = engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 13),
            strategy_return=Decimal("0.01"),
            benchmark_return=Decimal("0.00"),
        )
    )

    second = engine.calculate(
        AttributionInput(
            strategy_id="strategy-002",
            trade_date=date(2026, 8, 14),
            strategy_return=Decimal("0.02"),
            benchmark_return=Decimal("0.00"),
        )
    )

    builder = AttributionReportBuilder()

    with pytest.raises(ValueError):
        builder.build([first, second])

from datetime import date
from decimal import Decimal

from services.attribution import AttributionService


def test_service_builds_attribution_input():
    service = AttributionService()

    result = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 14),
        strategy_return="0.10",
        benchmark_return="0.04",
        gross_exposure="1.50",
        net_exposure="0.80",
        trading_pnl="0.05",
        financing_pnl="0.01",
        fee_pnl="-0.002",
        other_pnl="0.003",
    )

    assert result.strategy_id == "alpha-001"
    assert result.strategy_return == Decimal("0.10")
    assert result.benchmark_return == Decimal("0.04")
    assert result.active_return == Decimal("0.06")

    assert result.gross_exposure == Decimal("1.50")
    assert result.net_exposure == Decimal("0.80")


def test_service_builds_period_report():
    service = AttributionService()

    day_1 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 13),
        strategy_return="0.05",
        benchmark_return="0.02",
        trading_pnl="0.02",
    )

    day_2 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 14),
        strategy_return="0.03",
        benchmark_return="0.01",
        trading_pnl="0.015",
    )

    report = service.build_period_report(
        [day_1, day_2]
    )

    assert report.strategy_id == "alpha-001"
    assert report.observation_count == 2

    assert report.strategy_return == Decimal("0.0815")
    assert report.benchmark_return == Decimal("0.0302")

    assert report.trading_contribution == Decimal("0.035")

    assert report.attribution_check == Decimal("0")


def test_service_record_and_query():
    service = AttributionService()

    day_1 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 13),
        strategy_return="0.05",
        benchmark_return="0.02",
        trading_pnl="0.02",
    )

    day_2 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 14),
        strategy_return="0.03",
        benchmark_return="0.01",
        trading_pnl="0.015",
    )

    service.record_batch(
        [day_1, day_2]
    )

    records = service.get_daily(
        strategy_id="alpha-001",
    )

    assert len(records) == 2

    latest = service.get_latest(
        "alpha-001"
    )

    assert latest is not None
    assert latest.trade_date == date(2026, 8, 14)


def test_service_period_report_from_repository():
    service = AttributionService()

    day_1 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 13),
        strategy_return="0.05",
        benchmark_return="0.02",
        trading_pnl="0.02",
    )

    day_2 = service.attribute(
        strategy_id="alpha-001",
        trade_date=date(2026, 8, 14),
        strategy_return="0.03",
        benchmark_return="0.01",
        trading_pnl="0.015",
    )

    service.record_batch(
        [day_1, day_2]
    )

    report = service.get_period_report(
        strategy_id="alpha-001",
        start_date=date(2026, 8, 13),
        end_date=date(2026, 8, 14),
    )

    assert report.strategy_id == "alpha-001"
    assert report.observation_count == 2
    assert report.strategy_return == Decimal("0.0815")

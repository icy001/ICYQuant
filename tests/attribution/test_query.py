from datetime import date
from decimal import Decimal

from services.attribution import (
    AttributionEngine,
    AttributionInput,
    AttributionQuery,
    AttributionQueryService,
    AttributionRepository,
)


def make_result(
    trade_date: date,
    strategy_return: str,
    benchmark_return: str,
):
    engine = AttributionEngine()

    return engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=trade_date,
            strategy_return=Decimal(strategy_return),
            benchmark_return=Decimal(benchmark_return),
        )
    )


def test_query_daily():
    repository = AttributionRepository()

    repository.save_batch(
        [
            make_result(
                date(2026, 8, 13),
                "0.05",
                "0.02",
            ),
            make_result(
                date(2026, 8, 14),
                "0.03",
                "0.01",
            ),
        ]
    )

    query_service = AttributionQueryService(
        repository
    )

    query = AttributionQuery(
        strategy_id="strategy-001",
        start_date=date(2026, 8, 13),
        end_date=date(2026, 8, 14),
    )

    results = query_service.get_daily(query)

    assert len(results) == 2


def test_query_period_report():
    repository = AttributionRepository()

    repository.save_batch(
        [
            make_result(
                date(2026, 8, 13),
                "0.05",
                "0.02",
            ),
            make_result(
                date(2026, 8, 14),
                "0.03",
                "0.01",
            ),
        ]
    )

    query_service = AttributionQueryService(
        repository
    )

    report = query_service.get_period_report(
        AttributionQuery(
            strategy_id="strategy-001",
        )
    )

    assert report.observation_count == 2
    assert report.strategy_return == Decimal("0.0815")


def test_get_latest():
    repository = AttributionRepository()

    repository.save_batch(
        [
            make_result(
                date(2026, 8, 13),
                "0.05",
                "0.02",
            ),
            make_result(
                date(2026, 8, 14),
                "0.03",
                "0.01",
            ),
        ]
    )

    query_service = AttributionQueryService(
        repository
    )

    latest = query_service.get_latest(
        "strategy-001"
    )

    assert latest is not None
    assert latest.trade_date == date(2026, 8, 14)

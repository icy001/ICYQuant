from datetime import date
from decimal import Decimal

from services.attribution import (
    AttributionEngine,
    AttributionInput,
    AttributionRepository,
)


def make_result(
    strategy_id: str,
    trade_date: date,
):
    engine = AttributionEngine()

    return engine.calculate(
        AttributionInput(
            strategy_id=strategy_id,
            trade_date=trade_date,
            strategy_return=Decimal("0.02"),
            benchmark_return=Decimal("0.01"),
        )
    )


def test_save_and_get():
    repository = AttributionRepository()

    result = make_result(
        "strategy-001",
        date(2026, 8, 14),
    )

    repository.save(result)

    loaded = repository.get(
        "strategy-001",
        date(2026, 8, 14),
    )

    assert loaded == result


def test_list_is_sorted_by_date():
    repository = AttributionRepository()

    first = make_result(
        "strategy-001",
        date(2026, 8, 13),
    )

    second = make_result(
        "strategy-001",
        date(2026, 8, 14),
    )

    repository.save(second)
    repository.save(first)

    results = repository.list(
        strategy_id="strategy-001",
    )

    assert results == [first, second]


def test_list_supports_date_range():
    repository = AttributionRepository()

    records = [
        make_result(
            "strategy-001",
            date(2026, 8, 12),
        ),
        make_result(
            "strategy-001",
            date(2026, 8, 13),
        ),
        make_result(
            "strategy-001",
            date(2026, 8, 14),
        ),
    ]

    repository.save_batch(records)

    results = repository.list(
        strategy_id="strategy-001",
        start_date=date(2026, 8, 13),
        end_date=date(2026, 8, 14),
    )

    assert len(results) == 2
    assert results[0].trade_date == date(2026, 8, 13)
    assert results[1].trade_date == date(2026, 8, 14)


def test_strategy_records_are_isolated():
    repository = AttributionRepository()

    repository.save(
        make_result(
            "strategy-001",
            date(2026, 8, 14),
        )
    )

    repository.save(
        make_result(
            "strategy-002",
            date(2026, 8, 14),
        )
    )

    results = repository.list(
        strategy_id="strategy-001",
    )

    assert len(results) == 1
    assert results[0].strategy_id == "strategy-001"


def test_delete():
    repository = AttributionRepository()

    repository.save(
        make_result(
            "strategy-001",
            date(2026, 8, 14),
        )
    )

    assert repository.delete(
        "strategy-001",
        date(2026, 8, 14),
    )

    assert repository.get(
        "strategy-001",
        date(2026, 8, 14),
    ) is None


def test_count():
    repository = AttributionRepository()

    repository.save_batch(
        [
            make_result(
                "strategy-001",
                date(2026, 8, 13),
            ),
            make_result(
                "strategy-001",
                date(2026, 8, 14),
            ),
            make_result(
                "strategy-002",
                date(2026, 8, 14),
            ),
        ]
    )

    assert repository.count() == 3
    assert repository.count("strategy-001") == 2
    assert repository.count("strategy-002") == 1

from datetime import date
from decimal import Decimal

from services.attribution import (
    AttributionEngine,
    AttributionInput,
)


def test_active_return_is_strategy_minus_benchmark():
    engine = AttributionEngine()

    result = engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 14),
            strategy_return=Decimal("0.08"),
            benchmark_return=Decimal("0.03"),
        )
    )

    assert result.active_return == Decimal("0.05")


def test_contribution_decomposition():
    engine = AttributionEngine()

    result = engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 14),
            strategy_return=Decimal("0.08"),
            benchmark_return=Decimal("0.03"),
            trading_pnl=Decimal("0.04"),
            financing_pnl=Decimal("0.005"),
            fee_pnl=Decimal("-0.002"),
            other_pnl=Decimal("0.001"),
        )
    )

    assert result.active_return == Decimal("0.05")

    assert result.total_contribution == Decimal("0.044")

    assert result.residual == Decimal("0.006")


def test_zero_contribution_equals_active_return_residual():
    engine = AttributionEngine()

    result = engine.calculate(
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 14),
            strategy_return=Decimal("0.05"),
            benchmark_return=Decimal("0.02"),
        )
    )

    assert result.total_contribution == Decimal("0")
    assert result.residual == Decimal("0.03")


def test_batch_attribution():
    engine = AttributionEngine()

    records = [
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 13),
            strategy_return=Decimal("0.02"),
            benchmark_return=Decimal("0.01"),
        ),
        AttributionInput(
            strategy_id="strategy-001",
            trade_date=date(2026, 8, 14),
            strategy_return=Decimal("0.03"),
            benchmark_return=Decimal("0.01"),
        ),
    ]

    results = engine.calculate_batch(records)

    assert len(results) == 2
    assert results[0].active_return == Decimal("0.01")
    assert results[1].active_return == Decimal("0.02")

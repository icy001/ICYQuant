"""Tests for the reconciliation repair executor."""

from dataclasses import dataclass
from decimal import Decimal

from services.reconciliation.models.difference import (
    Difference,
    DifferenceType,
)
from services.reconciliation.models.repair import (
    RepairActionType,
    RepairPlan,
)
from services.reconciliation.position_builder import ExecutionPositionBuilder
from services.reconciliation.repair_executor import RepairExecutor


@dataclass(frozen=True)
class FillEvent:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal


def make_difference(
    difference_type: DifferenceType,
    expected: Decimal,
    actual: Decimal,
) -> Difference:
    return Difference(
        type=difference_type,
        expected=expected,
        actual=actual,
        delta=actual - expected,
    )


def make_plan(
    action: RepairActionType,
    reason: str = "test repair plan",
    differences: tuple[Difference, ...] = (),
) -> RepairPlan:
    return RepairPlan(
        action=action,
        reason=reason,
        differences=differences,
    )


def make_events() -> list[FillEvent]:
    return [
        FillEvent(
            symbol="AAPL",
            side="BUY",
            quantity=Decimal("100"),
            price=Decimal("150"),
        ),
        FillEvent(
            symbol="AAPL",
            side="SELL",
            quantity=Decimal("20"),
            price=Decimal("180"),
        ),
    ]


def test_rebuild_position_from_execution_events():
    difference = make_difference(
        DifferenceType.QUANTITY_MISMATCH,
        expected=Decimal("80"),
        actual=Decimal("60"),
    )
    plan = make_plan(
        RepairActionType.REBUILD_POSITION,
        reason="Quantity mismatch",
        differences=(difference,),
    )

    result = RepairExecutor(ExecutionPositionBuilder()).execute(
        plan=plan,
        events=make_events(),
    )

    assert result.action == RepairActionType.REBUILD_POSITION
    assert result.success is True
    assert result.reason == "Position rebuilt from execution events"
    assert result.rebuilt_position is not None
    assert result.rebuilt_position.symbol == "AAPL"
    assert result.rebuilt_position.quantity == Decimal("80")


def test_rebuild_position_computes_average_price_and_realized_pnl():
    difference = make_difference(
        DifferenceType.REALIZED_PNL_MISMATCH,
        expected=Decimal("600"),
        actual=Decimal("0"),
    )
    plan = make_plan(
        RepairActionType.REBUILD_POSITION,
        reason="Realized PnL mismatch",
        differences=(difference,),
    )

    result = RepairExecutor(ExecutionPositionBuilder()).execute(
        plan=plan,
        events=make_events(),
    )

    assert result.success is True
    assert result.rebuilt_position is not None
    assert result.rebuilt_position.average_price == Decimal("150")
    assert result.rebuilt_position.realized_pnl == Decimal("600")


def test_no_action_does_not_rebuild():
    plan = make_plan(RepairActionType.NO_ACTION)

    result = RepairExecutor(ExecutionPositionBuilder()).execute(
        plan=plan,
        events=make_events(),
    )

    assert result.action == RepairActionType.NO_ACTION
    assert result.success is True
    assert result.rebuilt_position is None
    assert result.reason == "No repair required"


def test_manual_review_does_not_auto_repair():
    plan = make_plan(RepairActionType.MANUAL_REVIEW)

    result = RepairExecutor(ExecutionPositionBuilder()).execute(
        plan=plan,
        events=make_events(),
    )

    assert result.action == RepairActionType.MANUAL_REVIEW
    assert result.success is False
    assert result.rebuilt_position is None
    assert result.reason == "Manual review required"


def test_unsupported_action_fails_without_rebuild():
    plan = make_plan(RepairActionType.REPLAY_EVENTS)

    result = RepairExecutor(ExecutionPositionBuilder()).execute(
        plan=plan,
        events=make_events(),
    )

    assert result.action == RepairActionType.REPLAY_EVENTS
    assert result.success is False
    assert result.rebuilt_position is None
    assert "Unsupported repair action" in result.reason

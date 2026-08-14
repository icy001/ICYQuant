"""Tests for the reconciliation service pipeline."""

from dataclasses import dataclass
from decimal import Decimal

from services.reconciliation.models.difference import DifferenceType
from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.models.repair import (
    RepairActionType,
    RepairPlan,
    RepairStatus,
)
from services.reconciliation.models.snapshot import PositionSnapshot
from services.reconciliation.models.status import ReconciliationStatus
from services.reconciliation.position_builder import ExecutionPositionBuilder
from services.reconciliation.repair_executor import (
    RepairExecutor,
    RepairResult,
)
from services.reconciliation.service import ReconciliationService


@dataclass(frozen=True)
class FillEvent:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal


def make_events() -> list[FillEvent]:
    return [
        FillEvent(
            symbol="AAPL",
            side="BUY",
            quantity=Decimal("100"),
            price=Decimal("150"),
        ),
    ]


def make_snapshot(
    quantity: Decimal,
    average_price: Decimal = Decimal("150"),
    realized_pnl: Decimal = Decimal("0"),
) -> PositionSnapshot:
    return PositionSnapshot(
        symbol="AAPL",
        quantity=quantity,
        average_price=average_price,
        realized_pnl=realized_pnl,
    )


def test_service_detects_quantity_mismatch_and_plans_rebuild():
    service = ReconciliationService()
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile_and_verify(events, snapshot)

    assert result.status == ReconciliationStatus.MISMATCH
    assert len(result.differences) == 1
    assert result.differences[0].type == DifferenceType.QUANTITY_MISMATCH
    assert result.differences[0].delta == Decimal("-20")

    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.REBUILD_POSITION


def test_service_rebuilds_position_from_execution_events():
    service = ReconciliationService()
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile_and_verify(events, snapshot)

    assert result.repair_result is not None
    assert result.repair_result.success is True
    assert result.repair_result.rebuilt_position is not None
    assert result.repair_result.rebuilt_position.quantity == Decimal("100")
    assert result.repair_result.rebuilt_position.symbol == "AAPL"
    assert result.repair_status == RepairStatus.VERIFIED
    assert result.repair_verification is not None
    assert result.repair_verification.verified is True


def test_service_matched_requires_no_action():
    service = ReconciliationService()
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("100"))

    result = service.reconcile_and_verify(events, snapshot)

    assert result.status == ReconciliationStatus.MATCHED
    assert result.differences == ()
    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.NO_ACTION
    assert result.repair_result is None
    assert result.repair_status == RepairStatus.NOT_REQUIRED


def test_service_reconcile_executes_rebuild_when_planned():
    service = ReconciliationService()
    events = make_events()
    expected = ExecutionPositionBuilder().build(events)
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile(expected, snapshot, events)

    assert result.status == ReconciliationStatus.MISMATCH
    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.REBUILD_POSITION
    assert result.repair_result is not None
    assert result.repair_result.success is True
    assert result.repair_result.rebuilt_position is not None
    assert result.repair_result.rebuilt_position.quantity == Decimal("100")
    assert result.repair_status == RepairStatus.EXECUTED


def test_service_unknown_mismatch_requires_manual_review():
    plan = RepairPlan(
        action=RepairActionType.MANUAL_REVIEW,
        reason="Unknown reconciliation difference requires manual review",
        differences=(),
    )

    class _FixedPlanner:
        def plan(self, result):
            return plan

    service = ReconciliationService(planner=_FixedPlanner())
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile_and_verify(events, snapshot)

    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.MANUAL_REVIEW
    assert result.repair_result is None
    assert result.repair_status == RepairStatus.MANUAL_REVIEW


def test_service_verification_stops_after_max_repair_attempts():
    calls = {"count": 0}

    class _BrokenExecutor:
        def execute(
            self,
            plan,
            events,
            current_position=None,
            reconciliation_id=None,
        ):
            calls["count"] += 1
            rebuilt = ExecutionPosition(
                symbol="AAPL",
                quantity=Decimal("999"),
                average_price=Decimal("150"),
                realized_pnl=Decimal("0"),
            )
            return RepairResult(
                action=plan.action,
                success=True,
                rebuilt_position=rebuilt,
                reason="Position rebuilt from execution events",
            )

    service = ReconciliationService(repair_executor=_BrokenExecutor())
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile_and_verify(events, snapshot)

    # 重建后二次验证仍然 mismatch：停止自动修复 → MANUAL_REVIEW
    assert calls["count"] == 1
    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.MANUAL_REVIEW
    assert "still mismatched" in result.repair_plan.reason
    assert result.repair_result is not None
    assert result.repair_result.success is True
    assert result.repair_status == RepairStatus.MANUAL_REVIEW


def test_service_execution_failure_marks_repair_failed():
    class _ThrowingBuilder:
        def build(self, events):
            raise RuntimeError("rebuild failed")

    service = ReconciliationService(
        repair_executor=RepairExecutor(_ThrowingBuilder()),
    )
    events = make_events()
    snapshot = make_snapshot(quantity=Decimal("80"))

    result = service.reconcile_and_verify(events, snapshot)

    assert result.repair_plan is not None
    assert result.repair_plan.action == RepairActionType.REBUILD_POSITION
    assert result.repair_result is not None
    assert result.repair_result.success is False
    assert result.repair_result.rebuilt_position is None
    assert result.repair_result.reason == "rebuild failed"
    assert result.repair_status == RepairStatus.FAILED

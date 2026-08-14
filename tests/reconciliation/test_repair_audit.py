"""Tests for repair record auditing."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from services.reconciliation.id_generator import IdGenerator
from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.models.repair import (
    RepairActionType,
    RepairPlan,
    RepairStatus,
)
from services.reconciliation.models.repair_verification import RepairVerification
from services.reconciliation.position_builder import ExecutionPositionBuilder
from services.reconciliation.repair_executor import RepairExecutor
from services.reconciliation.repair_repository import InMemoryRepairRepository


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
        FillEvent(
            symbol="AAPL",
            side="SELL",
            quantity=Decimal("20"),
            price=Decimal("180"),
        ),
    ]


def make_plan() -> RepairPlan:
    return RepairPlan(
        action=RepairActionType.REBUILD_POSITION,
        reason="Quantity mismatch",
        differences=(),
    )


def make_current_position() -> ExecutionPosition:
    return ExecutionPosition(
        symbol="AAPL",
        quantity=Decimal("60"),
        average_price=Decimal("180"),
        realized_pnl=Decimal("900"),
    )


def make_executor(
    repo: InMemoryRepairRepository,
) -> RepairExecutor:
    return RepairExecutor(
        position_builder=ExecutionPositionBuilder(),
        repository=repo,
        id_generator=IdGenerator("REPAIR"),
        now_provider=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )


def test_create_repair_record():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    result = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    assert result.success is True
    assert result.repair_id == "REPAIR-20260814-000001"
    record = repo.get(result.repair_id)
    assert record is not None
    assert record.reconciliation_id == "REC-20260814-000001"
    assert record.action == RepairActionType.REBUILD_POSITION
    assert record.status == RepairStatus.EXECUTED
    assert record.attempt == 1


def test_capture_before_state():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    result = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    record = repo.get(result.repair_id)
    assert record.before_quantity == Decimal("60")
    assert record.before_average_price == Decimal("180")
    assert record.before_realized_pnl == Decimal("900")


def test_capture_after_state():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    result = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    record = repo.get(result.repair_id)
    assert record.after_quantity == Decimal("80")
    assert record.after_average_price == Decimal("150")
    assert record.after_realized_pnl == Decimal("600")


def test_repair_status_transition():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    result = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    assert result.record is not None
    assert result.record.status == RepairStatus.EXECUTED

    verification = RepairVerification(
        verified=True,
        reconciliation_status="MATCHED",
        verified_at=datetime(2026, 8, 14, 12, 1, tzinfo=timezone.utc),
        reason="Rebuilt position matches execution-derived state",
    )
    finalised = executor.complete_verification(
        result.repair_id,
        verification,
    )

    assert finalised is not None
    assert finalised.status == RepairStatus.VERIFIED
    assert repo.get(result.repair_id).status == RepairStatus.VERIFIED


def test_failed_repair_is_audited():
    class _BrokenBuilder:
        def build(self, events):
            raise RuntimeError("rebuild failed")

    repo = InMemoryRepairRepository()
    executor = RepairExecutor(
        position_builder=_BrokenBuilder(),
        repository=repo,
        id_generator=IdGenerator("REPAIR"),
        now_provider=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )

    result = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    assert result.success is False
    assert result.rebuilt_position is None
    assert result.reason == "rebuild failed"

    record = repo.get(result.repair_id)
    assert record is not None
    assert record.status == RepairStatus.FAILED
    assert record.completed_at is not None
    assert record.after_quantity is None


def test_manual_review_is_not_executed():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)
    plan = RepairPlan(
        action=RepairActionType.MANUAL_REVIEW,
        reason="Manual review required",
        differences=(),
    )

    result = executor.execute(
        plan=plan,
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    assert result.success is False
    assert result.rebuilt_position is None
    assert result.record is None
    assert repo.list_by_reconciliation("REC-20260814-000001") == []


def test_repair_idempotency():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    first = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )
    second = executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )

    records = repo.list_by_reconciliation("REC-20260814-000001")
    assert len(records) == 1
    assert first.repair_id == second.repair_id


def test_reconciliation_repair_lookup():
    repo = InMemoryRepairRepository()
    executor = make_executor(repo)

    executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000001",
    )
    executor.execute(
        plan=make_plan(),
        events=make_events(),
        current_position=make_current_position(),
        reconciliation_id="REC-20260814-000002",
    )

    records = repo.list_by_reconciliation("REC-20260814-000001")
    assert len(records) == 1
    assert records[0].repair_id == "REPAIR-20260814-000001"
    assert records[0].reconciliation_id == "REC-20260814-000001"

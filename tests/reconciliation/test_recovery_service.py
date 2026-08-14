"""Tests for the recovery service pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from services.reconciliation.id_generator import IdGenerator
from services.reconciliation.models.difference import (
    Difference,
    DifferenceType,
)
from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.models.repair import (
    RepairActionType,
    RepairStatus,
)
from services.reconciliation.models.result import ReconciliationResult
from services.reconciliation.models.status import ReconciliationStatus
from services.reconciliation.position_builder import ExecutionPositionBuilder
from services.reconciliation.recovery_service import RecoveryService
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
    ]


def make_current_position() -> ExecutionPosition:
    return ExecutionPosition(
        symbol="AAPL",
        quantity=Decimal("80"),
        average_price=Decimal("150"),
        realized_pnl=Decimal("0"),
    )


def make_matched_reconciliation() -> ReconciliationResult:
    return ReconciliationResult(
        symbol="AAPL",
        status=ReconciliationStatus.MATCHED,
        id="REC-20260814-000001",
    )


def make_mismatch_reconciliation() -> ReconciliationResult:
    difference = Difference(
        type=DifferenceType.QUANTITY_MISMATCH,
        expected=Decimal("100"),
        actual=Decimal("80"),
        delta=Decimal("-20"),
    )
    return ReconciliationResult(
        symbol="AAPL",
        status=ReconciliationStatus.MISMATCH,
        id="REC-20260814-000001",
        differences=(difference,),
    )


def make_unknown_reconciliation() -> ReconciliationResult:
    difference = Difference(
        type=DifferenceType.UNKNOWN_MISMATCH,
        expected=Decimal("0"),
        actual=Decimal("1"),
        delta=Decimal("1"),
    )
    return ReconciliationResult(
        symbol="AAPL",
        status=ReconciliationStatus.MISMATCH,
        id="REC-20260814-000003",
        differences=(difference,),
    )


def make_service() -> tuple[RecoveryService, InMemoryRepairRepository]:
    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=position_builder,
        repository=repo,
        id_generator=IdGenerator("REPAIR"),
        now_provider=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    service = RecoveryService(
        position_builder=position_builder,
        repair_executor=executor,
        now_provider=lambda: datetime(2026, 8, 14, 12, 1, tzinfo=timezone.utc),
    )
    return service, repo


def test_no_action_requires_no_repair():
    service, repo = make_service()

    outcome = service.recover(
        reconciliation=make_matched_reconciliation(),
        current_position=make_current_position(),
        events=make_events(),
    )

    assert outcome.reconciliation_id == "REC-20260814-000001"
    assert outcome.plan.action == RepairActionType.NO_ACTION
    assert outcome.repair_result is None
    assert outcome.verification is None
    assert outcome.repair_status == RepairStatus.NOT_REQUIRED
    assert repo.list_by_reconciliation("REC-20260814-000001") == []


def test_successful_repair_verification():
    service, repo = make_service()

    outcome = service.recover(
        reconciliation=make_mismatch_reconciliation(),
        current_position=make_current_position(),
        events=make_events(),
    )

    assert outcome.plan.action == RepairActionType.REBUILD_POSITION
    assert outcome.repair_result is not None
    assert outcome.repair_result.success is True
    assert outcome.repair_result.rebuilt_position is not None
    assert outcome.repair_result.rebuilt_position.quantity == Decimal("100")

    assert outcome.verification is not None
    assert outcome.verification.verified is True
    assert outcome.verification.reconciliation_status == "MATCHED"
    assert outcome.repair_status == RepairStatus.VERIFIED

    record = repo.get(outcome.repair_result.repair_id)
    assert record is not None
    assert record.status == RepairStatus.VERIFIED
    assert record.after_quantity == Decimal("100")


def test_failed_repair_is_audited_not_crashed():
    class _BrokenBuilder:
        def build(self, events):
            raise RuntimeError("rebuild failed")

    repo = InMemoryRepairRepository()
    service = RecoveryService(
        position_builder=ExecutionPositionBuilder(),
        repair_executor=RepairExecutor(
            position_builder=_BrokenBuilder(),
            repository=repo,
        ),
    )

    outcome = service.recover(
        reconciliation=make_mismatch_reconciliation(),
        current_position=make_current_position(),
        events=make_events(),
    )

    assert outcome.repair_status == RepairStatus.FAILED
    assert outcome.repair_result is not None
    assert outcome.repair_result.success is False
    assert outcome.verification is None

    records = repo.list_by_reconciliation("REC-20260814-000001")
    assert len(records) == 1
    assert records[0].status == RepairStatus.FAILED


def test_manual_review_is_not_executed():
    service, repo = make_service()

    outcome = service.recover(
        reconciliation=make_unknown_reconciliation(),
        current_position=make_current_position(),
        events=make_events(),
    )

    assert outcome.plan.action == RepairActionType.MANUAL_REVIEW
    assert outcome.repair_result is None
    assert outcome.verification is None
    assert outcome.repair_status == RepairStatus.MANUAL_REVIEW
    assert repo.list_by_reconciliation("REC-20260814-000003") == []

"""Tests for the self-healing coordinator."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from services.reconciliation.id_generator import IdGenerator
from services.reconciliation.lifecycle import ReconciliationLifecycle
from services.reconciliation.models.difference import (
    Difference,
    DifferenceType,
)
from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.models.repair import RepairStatus
from services.reconciliation.models.result import ReconciliationResult
from services.reconciliation.models.status import ReconciliationStatus
from services.reconciliation.position_builder import ExecutionPositionBuilder
from services.reconciliation.recovery_metrics import RecoveryMetrics
from services.reconciliation.repair_executor import RepairExecutor
from services.reconciliation.repair_repository import InMemoryRepairRepository
from services.reconciliation.self_healing import SelfHealingCoordinator


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


def make_matched_position() -> ExecutionPosition:
    return ExecutionPosition(
        symbol="AAPL",
        quantity=Decimal("100"),
        average_price=Decimal("150"),
        realized_pnl=Decimal("0"),
    )


def make_mismatch_position() -> ExecutionPosition:
    return ExecutionPosition(
        symbol="AAPL",
        quantity=Decimal("80"),
        average_price=Decimal("150"),
        realized_pnl=Decimal("0"),
    )


def make_reconciliation() -> ReconciliationResult:
    return ReconciliationResult(
        symbol="AAPL",
        status=ReconciliationStatus.MISMATCH,
        id="REC-20260814-000001",
    )


def make_coordinator() -> tuple[SelfHealingCoordinator, InMemoryRepairRepository]:
    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=position_builder,
        repository=repo,
        id_generator=IdGenerator("REPAIR"),
        now_provider=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    coordinator = SelfHealingCoordinator(
        position_builder=position_builder,
        repair_executor=executor,
        now_provider=lambda: datetime(2026, 8, 14, 12, 1, tzinfo=timezone.utc),
    )
    return coordinator, repo


def test_matched_state_requires_no_repair():
    coordinator, repo = make_coordinator()

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_matched_position(),
        events=make_events(),
    )

    assert result.lifecycle == ReconciliationLifecycle.MATCHED
    assert result.repaired is False
    assert result.verified is True
    assert result.repair_id is None
    assert result.reason == "Reconciliation matched; no repair required"
    assert repo.list_by_reconciliation("REC-20260814-000001") == []


def test_self_healing_returns_recovered():
    coordinator, repo = make_coordinator()

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert result.lifecycle == ReconciliationLifecycle.RECOVERED
    assert result.repaired is True
    assert result.verified is True
    assert result.repair_id is not None

    record = repo.get(result.repair_id)
    assert record is not None
    assert record.status == RepairStatus.VERIFIED
    assert record.after_quantity == Decimal("100")


def test_repair_success_requires_verification():
    class _VerificationFailComparator:
        def compare(self, expected, actual):
            return ReconciliationResult(
                symbol=expected.symbol,
                status=ReconciliationStatus.MISMATCH,
                differences=(
                    Difference(
                        type=DifferenceType.QUANTITY_MISMATCH,
                        expected=expected.quantity,
                        actual=actual.quantity,
                        delta=actual.quantity - expected.quantity,
                    ),
                ),
            )

    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=position_builder,
        repository=repo,
    )
    coordinator = SelfHealingCoordinator(
        position_builder=position_builder,
        comparator=_VerificationFailComparator(),
        repair_executor=executor,
    )

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    # Repair succeeded (rebuilt position produced), but the post-repair
    # reconciliation still shows MISMATCH -> MANUAL_REVIEW, NOT RECOVERED.
    assert result.repaired is True
    assert result.verified is False
    assert result.lifecycle == ReconciliationLifecycle.MANUAL_REVIEW


def test_failed_verification_enters_manual_review():
    class _AlwaysMismatchComparator:
        def compare(self, expected, actual):
            return ReconciliationResult(
                symbol=expected.symbol,
                status=ReconciliationStatus.MISMATCH,
                differences=(),
            )

    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=position_builder,
        repository=repo,
    )
    coordinator = SelfHealingCoordinator(
        position_builder=position_builder,
        comparator=_AlwaysMismatchComparator(),
        repair_executor=executor,
    )

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert result.lifecycle == ReconciliationLifecycle.MANUAL_REVIEW
    assert result.verified is False


def test_manual_review_plan_is_not_executed():
    class _UnknownMismatchComparator:
        def compare(self, expected, actual):
            return ReconciliationResult(
                symbol=expected.symbol,
                status=ReconciliationStatus.MISMATCH,
                differences=(
                    Difference(
                        type=DifferenceType.UNKNOWN_MISMATCH,
                        expected=Decimal("0"),
                        actual=Decimal("1"),
                        delta=Decimal("1"),
                    ),
                ),
            )

    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=position_builder,
        repository=repo,
    )
    coordinator = SelfHealingCoordinator(
        position_builder=position_builder,
        comparator=_UnknownMismatchComparator(),
        repair_executor=executor,
    )

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert result.lifecycle == ReconciliationLifecycle.MANUAL_REVIEW
    assert result.repaired is False
    assert result.verified is False
    assert result.repair_id is None
    assert repo.list_by_reconciliation("REC-20260814-000001") == []


def test_failed_repair_enters_failed():
    class _BrokenBuilder:
        def build(self, events):
            raise RuntimeError("rebuild failed")

    repo = InMemoryRepairRepository()
    position_builder = ExecutionPositionBuilder()
    executor = RepairExecutor(
        position_builder=_BrokenBuilder(),
        repository=repo,
    )
    coordinator = SelfHealingCoordinator(
        position_builder=position_builder,
        repair_executor=executor,
    )

    result = coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert result.lifecycle == ReconciliationLifecycle.FAILED
    assert result.repaired is False
    assert result.verified is False

    records = repo.list_by_reconciliation("REC-20260814-000001")
    assert len(records) == 1
    assert records[0].status == RepairStatus.FAILED


def test_lifecycle_reaches_recovered_after_verification():
    coordinator, _ = make_coordinator()

    coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert coordinator.lifecycle == ReconciliationLifecycle.RECOVERED


def test_metrics_are_recorded():
    metrics = RecoveryMetrics()
    coordinator = SelfHealingCoordinator(
        position_builder=ExecutionPositionBuilder(),
        metrics=metrics,
    )

    coordinator.recover(
        reconciliation=make_reconciliation(),
        current_position=make_mismatch_position(),
        events=make_events(),
    )

    assert metrics.reconciliation_total == 1
    assert metrics.reconciliation_mismatched == 1
    assert metrics.repair_total == 1
    assert metrics.repair_success_total == 1
    assert metrics.recovery_total == 1
    assert metrics.recovery_success_total == 1

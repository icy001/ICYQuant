"""Repair executor.

Executes a :class:`RepairPlan` by rebuilding the position from
execution events instead of mutating the existing position.

Execution events are the source of truth; a position is a rebuildable
state. Repair therefore never writes ``position.quantity = ...``.

Every executed repair is persisted as a :class:`RepairRecord`: the
before/after state, status transitions and failures are audited so the
whole recovery lifecycle can be traced, replayed and retried.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal

from .id_generator import IdGenerator
from .models.execution_position import ExecutionPosition
from .models.repair import (
    RepairActionType,
    RepairPlan,
    RepairStatus,
)
from .models.repair_record import RepairRecord
from .models.repair_verification import RepairVerification
from .position_builder import ExecutionPositionBuilder
from .repair_repository import (
    InMemoryRepairRepository,
    RepairRepository,
)

REPAIR_ATTEMPT = 1


@dataclass(frozen=True)
class RepairResult:
    action: RepairActionType
    success: bool
    rebuilt_position: ExecutionPosition | None
    reason: str
    repair_id: str | None = None
    reconciliation_id: str | None = None
    record: RepairRecord | None = None


class RepairExecutor:
    def __init__(
        self,
        position_builder: ExecutionPositionBuilder,
        repository: RepairRepository | None = None,
        id_generator: IdGenerator | None = None,
        now_provider=None,
    ) -> None:
        self.position_builder = position_builder
        self.repository = repository or InMemoryRepairRepository()
        self._id_generator = id_generator or IdGenerator("REPAIR")
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def execute(
        self,
        plan: RepairPlan,
        events,
        current_position: ExecutionPosition | None = None,
        reconciliation_id: str | None = None,
    ) -> RepairResult:
        if plan.action == RepairActionType.NO_ACTION:
            return RepairResult(
                action=plan.action,
                success=True,
                rebuilt_position=None,
                reason="No repair required",
                reconciliation_id=reconciliation_id,
            )

        if plan.action == RepairActionType.MANUAL_REVIEW:
            return RepairResult(
                action=plan.action,
                success=False,
                rebuilt_position=None,
                reason="Manual review required",
                reconciliation_id=reconciliation_id,
            )

        if plan.action != RepairActionType.REBUILD_POSITION:
            return RepairResult(
                action=plan.action,
                success=False,
                rebuilt_position=None,
                reason=f"Unsupported repair action: {plan.action}",
                reconciliation_id=reconciliation_id,
            )

        existing = self._find_existing(reconciliation_id)
        if existing is not None:
            return self._result_from_record(existing, events)

        repair_id = self._id_generator.generate(
            now=self._now_provider()
        )
        record = self._create_record(
            repair_id=repair_id,
            reconciliation_id=reconciliation_id or "",
            plan=plan,
            current_position=current_position,
        )
        self.repository.create(record)

        try:
            rebuilt = self.position_builder.build(events)
        except Exception as exc:
            failed = replace(
                record,
                status=RepairStatus.FAILED,
                completed_at=self._now_provider(),
            )
            self.repository.update(failed)
            return RepairResult(
                action=plan.action,
                success=False,
                rebuilt_position=None,
                reason=str(exc),
                repair_id=repair_id,
                reconciliation_id=record.reconciliation_id,
                record=failed,
            )

        completed = self._complete_record(
            record=record,
            rebuilt_position=rebuilt,
        )
        self.repository.update(completed)

        return RepairResult(
            action=plan.action,
            success=True,
            rebuilt_position=rebuilt,
            reason="Position rebuilt from execution events",
            repair_id=repair_id,
            reconciliation_id=record.reconciliation_id,
            record=completed,
        )

    def complete_verification(
        self,
        repair_id: str,
        verification: RepairVerification,
    ) -> RepairRecord | None:
        """Persist the verification outcome and finalise the record status."""
        record = self.repository.get(repair_id)
        if record is None:
            return None

        status = (
            RepairStatus.VERIFIED
            if verification.verified
            else RepairStatus.MANUAL_REVIEW
        )
        finalised = replace(
            record,
            status=status,
            completed_at=self._now_provider(),
        )
        self.repository.update(finalised)
        return finalised

    def _find_existing(
        self,
        reconciliation_id: str | None,
    ) -> RepairRecord | None:
        if not reconciliation_id:
            return None
        records = self.repository.list_by_reconciliation(reconciliation_id)
        if not records:
            return None
        return records[0]

    def _result_from_record(
        self,
        record: RepairRecord,
        events,
    ) -> RepairResult:
        if record.status == RepairStatus.FAILED:
            return RepairResult(
                action=record.action,
                success=False,
                rebuilt_position=None,
                reason=record.reason,
                repair_id=record.repair_id,
                reconciliation_id=record.reconciliation_id,
                record=record,
            )

        rebuilt = self.position_builder.build(events)
        return RepairResult(
            action=record.action,
            success=True,
            rebuilt_position=rebuilt,
            reason=record.reason,
            repair_id=record.repair_id,
            reconciliation_id=record.reconciliation_id,
            record=record,
        )

    def _create_record(
        self,
        repair_id: str,
        reconciliation_id: str,
        plan: RepairPlan,
        current_position: ExecutionPosition | None,
    ) -> RepairRecord:
        before = self._capture(current_position)
        return RepairRecord(
            repair_id=repair_id,
            reconciliation_id=reconciliation_id,
            action=plan.action,
            status=RepairStatus.EXECUTING,
            reason=plan.reason,
            before_quantity=before[0],
            before_average_price=before[1],
            before_realized_pnl=before[2],
            after_quantity=None,
            after_average_price=None,
            after_realized_pnl=None,
            attempt=REPAIR_ATTEMPT,
            created_at=self._now_provider(),
            completed_at=None,
        )

    def _complete_record(
        self,
        record: RepairRecord,
        rebuilt_position: ExecutionPosition,
    ) -> RepairRecord:
        after = self._capture(rebuilt_position)
        return replace(
            record,
            status=RepairStatus.EXECUTED,
            after_quantity=after[0],
            after_average_price=after[1],
            after_realized_pnl=after[2],
            completed_at=self._now_provider(),
        )

    @staticmethod
    def _capture(
        position: ExecutionPosition | None,
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        if position is None:
            return None, None, None
        return (
            position.quantity,
            position.average_price,
            position.realized_pnl,
        )

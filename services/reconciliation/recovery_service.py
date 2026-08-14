"""Recovery service.

Orchestrates the full recovery pipeline:

    Planner -> Executor -> Verification -> Audit

A :class:`RepairRecord` is persisted for every executed repair and the
verification outcome is audited, so the whole recovery lifecycle can be
traced and replayed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .comparator import ExecutionPositionComparator
from .models.execution_position import ExecutionPosition
from .models.repair import (
    RepairActionType,
    RepairPlan,
    RepairStatus,
)
from .models.repair_verification import RepairVerification
from .models.result import ReconciliationResult
from .models.snapshot import PositionSnapshot
from .models.status import ReconciliationStatus
from .planner import RepairPlanner
from .position_builder import ExecutionPositionBuilder
from .repair_executor import (
    RepairExecutor,
    RepairResult,
)


@dataclass(frozen=True)
class RecoveryOutcome:
    reconciliation_id: str
    plan: RepairPlan
    repair_result: RepairResult | None
    verification: RepairVerification | None
    repair_status: RepairStatus


class RecoveryService:
    def __init__(
        self,
        planner: RepairPlanner | None = None,
        repair_executor: RepairExecutor | None = None,
        position_builder: ExecutionPositionBuilder | None = None,
        comparator: ExecutionPositionComparator | None = None,
        now_provider=None,
    ) -> None:
        self._position_builder = position_builder or ExecutionPositionBuilder()
        self._comparator = comparator or ExecutionPositionComparator()
        self._planner = planner or RepairPlanner()
        self._repair_executor = (
            repair_executor or RepairExecutor(self._position_builder)
        )
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def recover(
        self,
        reconciliation: ReconciliationResult,
        current_position: ExecutionPosition,
        events,
    ) -> RecoveryOutcome:
        plan = self._planner.plan(reconciliation)

        if plan.action == RepairActionType.NO_ACTION:
            return RecoveryOutcome(
                reconciliation_id=reconciliation.id,
                plan=plan,
                repair_result=None,
                verification=None,
                repair_status=RepairStatus.NOT_REQUIRED,
            )

        if plan.action == RepairActionType.MANUAL_REVIEW:
            return RecoveryOutcome(
                reconciliation_id=reconciliation.id,
                plan=plan,
                repair_result=None,
                verification=None,
                repair_status=RepairStatus.MANUAL_REVIEW,
            )

        repair_result = self._execute_safely(
            plan=plan,
            events=events,
            current_position=current_position,
            reconciliation_id=reconciliation.id,
        )

        if not repair_result.success:
            return RecoveryOutcome(
                reconciliation_id=reconciliation.id,
                plan=plan,
                repair_result=repair_result,
                verification=None,
                repair_status=RepairStatus.FAILED,
            )

        verification = self._verify(
            events=events,
            rebuilt=repair_result.rebuilt_position,
        )
        self._complete_verification(repair_result, verification)

        return RecoveryOutcome(
            reconciliation_id=reconciliation.id,
            plan=plan,
            repair_result=repair_result,
            verification=verification,
            repair_status=(
                RepairStatus.VERIFIED
                if verification.verified
                else RepairStatus.MANUAL_REVIEW
            ),
        )

    def _verify(
        self,
        events,
        rebuilt: ExecutionPosition,
    ) -> RepairVerification:
        expected = self._position_builder.build(events)
        result = self._comparator.compare(
            expected=expected,
            actual=self._to_snapshot(rebuilt),
        )
        verified = result.status == ReconciliationStatus.MATCHED

        return RepairVerification(
            verified=verified,
            reconciliation_status=result.status.value,
            verified_at=self._now_provider(),
            reason=(
                "Rebuilt position matches execution-derived state"
                if verified
                else "Position remains inconsistent after rebuild"
            ),
        )

    def _execute_safely(
        self,
        plan: RepairPlan,
        events,
        current_position: ExecutionPosition,
        reconciliation_id: str,
    ) -> RepairResult:
        try:
            return self._repair_executor.execute(
                plan=plan,
                events=events,
                current_position=current_position,
                reconciliation_id=reconciliation_id,
            )
        except Exception as exc:
            return RepairResult(
                action=plan.action,
                success=False,
                rebuilt_position=None,
                reason=f"Repair execution failed: {exc}",
                reconciliation_id=reconciliation_id,
            )

    def _complete_verification(
        self,
        repair_result: RepairResult,
        verification: RepairVerification,
    ) -> None:
        marker = getattr(
            self._repair_executor,
            "complete_verification",
            None,
        )
        if marker is None or repair_result.repair_id is None:
            return
        marker(repair_result.repair_id, verification)

    @staticmethod
    def _to_snapshot(position: ExecutionPosition) -> PositionSnapshot:
        return PositionSnapshot(
            symbol=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price,
            realized_pnl=position.realized_pnl,
        )

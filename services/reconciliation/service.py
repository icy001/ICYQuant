"""Reconciliation service.

Wires position rebuild, difference classification, repair planning
and repair execution into a single reconciliation pipeline.

Execution events are the source of truth: repair never mutates the
existing position, it rebuilds the position from events.

Every reconciliation carries a unique ``reconciliation_id`` and every
executed repair is persisted and verified (second reconciliation).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .comparator import ExecutionPositionComparator
from .id_generator import IdGenerator
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

MAX_REPAIR_ATTEMPTS = 1


class ReconciliationService:
    def __init__(
        self,
        position_builder: ExecutionPositionBuilder | None = None,
        comparator: ExecutionPositionComparator | None = None,
        planner: RepairPlanner | None = None,
        repair_executor: RepairExecutor | None = None,
        reconciliation_id_generator: IdGenerator | None = None,
        now_provider=None,
    ) -> None:
        self._position_builder = position_builder or ExecutionPositionBuilder()
        self._comparator = comparator or ExecutionPositionComparator()
        self._planner = planner or RepairPlanner()
        self._repair_executor = (
            repair_executor or RepairExecutor(self._position_builder)
        )
        self._reconciliation_id_generator = (
            reconciliation_id_generator or IdGenerator("REC")
        )
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def reconcile(
        self,
        expected: ExecutionPosition,
        actual: PositionSnapshot,
        events,
    ) -> ReconciliationResult:
        """Run a single reconciliation pass (compare, plan, execute rebuild)."""
        reconciliation_id = self._reconciliation_id_generator.generate()
        result = self._comparator.compare(
            expected=expected,
            actual=actual,
        )
        result = replace(result, id=reconciliation_id)
        plan = self._planner.plan(result)

        if plan.action == RepairActionType.NO_ACTION:
            return replace(
                result,
                repair_plan=plan,
                repair_status=RepairStatus.NOT_REQUIRED,
            )

        if plan.action == RepairActionType.MANUAL_REVIEW:
            return replace(
                result,
                repair_plan=plan,
                repair_status=RepairStatus.MANUAL_REVIEW,
            )

        repair_result = self._execute_safely(
            plan,
            events,
            reconciliation_id,
        )
        return replace(
            result,
            repair_plan=plan,
            repair_result=repair_result,
            repair_status=(
                RepairStatus.EXECUTED
                if repair_result.success
                else RepairStatus.FAILED
            ),
        )

    def reconcile_and_verify(
        self,
        events,
        snapshot: PositionSnapshot,
        reconciliation_id: str | None = None,
    ) -> ReconciliationResult:
        """Full pipeline: rebuild, then verify with a second reconciliation.

        A rebuild is executed at most ``MAX_REPAIR_ATTEMPTS`` times. If the
        verification reconciliation still reports a mismatch the automatic
        repair stops and the plan becomes ``MANUAL_REVIEW``.
        """
        reconciliation_id = (
            reconciliation_id or self._reconciliation_id_generator.generate()
        )
        expected = self._position_builder.build(events)
        result = self._comparator.compare(
            expected=expected,
            actual=snapshot,
        )
        result = replace(result, id=reconciliation_id)
        plan = self._planner.plan(result)

        if plan.action == RepairActionType.NO_ACTION:
            return replace(
                result,
                repair_plan=plan,
                repair_status=RepairStatus.NOT_REQUIRED,
            )

        if plan.action == RepairActionType.MANUAL_REVIEW:
            return replace(
                result,
                repair_plan=plan,
                repair_status=RepairStatus.MANUAL_REVIEW,
            )

        for _ in range(MAX_REPAIR_ATTEMPTS):
            repair_result = self._execute_safely(
                plan,
                events,
                reconciliation_id,
            )
            if not repair_result.success:
                return replace(
                    result,
                    repair_plan=plan,
                    repair_result=repair_result,
                    repair_status=RepairStatus.FAILED,
                )

            rebuilt = repair_result.rebuilt_position
            verified = self._comparator.compare(
                expected=expected,
                actual=self._to_snapshot(rebuilt),
            )
            verification = RepairVerification(
                verified=verified.status == ReconciliationStatus.MATCHED,
                reconciliation_status=verified.status.value,
                verified_at=self._now_provider(),
                reason=(
                    "Rebuilt position matches execution-derived state"
                    if verified.status == ReconciliationStatus.MATCHED
                    else "Position remains inconsistent after rebuild"
                ),
            )

            if verified.status == ReconciliationStatus.MATCHED:
                self._complete_verification(repair_result, verification)
                return replace(
                    result,
                    repair_plan=plan,
                    repair_result=repair_result,
                    repair_status=RepairStatus.VERIFIED,
                    repair_verification=verification,
                )

            review_plan = RepairPlan(
                action=RepairActionType.MANUAL_REVIEW,
                reason=(
                    "Position rebuilt from execution events but verification "
                    "reconciliation still mismatched"
                ),
                differences=verified.differences,
            )
            self._complete_verification(repair_result, verification)
            return replace(
                result,
                repair_plan=review_plan,
                repair_result=repair_result,
                repair_status=RepairStatus.MANUAL_REVIEW,
                repair_verification=verification,
            )

        return result

    def _execute_safely(
        self,
        plan: RepairPlan,
        events,
        reconciliation_id: str,
    ) -> RepairResult:
        try:
            return self._repair_executor.execute(
                plan=plan,
                events=events,
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

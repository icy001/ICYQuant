"""Self-healing coordinator (Commit 40 Part 1.5).

Unifies Comparator / Planner / Executor / Verifier / Audit / Lifecycle into
a single deterministic recovery workflow.

    Reconciliation
        -> Recovery
            -> Verification
                -> Self-Healing Lifecycle

Self-healing never "guesses" the correct state: a repair is always derived
from the source of truth (execution events) and must be re-verified before
the reconciliation is considered recovered.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .comparator import ExecutionPositionComparator
from .lifecycle import (
    ReconciliationLifecycle,
    ReconciliationLifecycleManager,
)
from .models.execution_position import ExecutionPosition
from .models.recovery_result import RecoveryResult
from .models.repair import RepairActionType
from .models.repair_verification import RepairVerification
from .models.result import ReconciliationResult
from .models.snapshot import PositionSnapshot
from .models.status import (
    ReconciliationLifecycle as Lifecycle,
)
from .models.status import (
    ReconciliationStatus,
)
from .planner import RepairPlanner
from .position_builder import ExecutionPositionBuilder
from .recovery_metrics import RecoveryMetrics
from .recovery_policy import RecoveryPolicy
from .repair_executor import (
    RepairExecutor,
    RepairResult,
)
from .safety_guard import (
    RecoverySafetyError,
    RecoverySafetyGuard,
)


class SelfHealingCoordinator:
    """Coordinates the full self-healing recovery lifecycle."""

    def __init__(
        self,
        position_builder: ExecutionPositionBuilder | None = None,
        comparator: ExecutionPositionComparator | None = None,
        planner: RepairPlanner | None = None,
        repair_executor: RepairExecutor | None = None,
        policy: RecoveryPolicy | None = None,
        safety_guard: RecoverySafetyGuard | None = None,
        lifecycle: ReconciliationLifecycleManager | None = None,
        metrics: RecoveryMetrics | None = None,
        now_provider=None,
    ) -> None:
        self._position_builder = position_builder or ExecutionPositionBuilder()
        self._comparator = comparator or ExecutionPositionComparator()
        self._planner = planner or RepairPlanner()
        self._repair_executor = (
            repair_executor or RepairExecutor(self._position_builder)
        )
        self._policy = policy or RecoveryPolicy()
        self._safety_guard = safety_guard or RecoverySafetyGuard()
        self._lifecycle = lifecycle or ReconciliationLifecycleManager()
        self._metrics = metrics or RecoveryMetrics()
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    @property
    def lifecycle(self) -> ReconciliationLifecycle:
        return self._lifecycle.state

    @property
    def metrics(self) -> RecoveryMetrics:
        return self._metrics

    def recover(
        self,
        reconciliation: ReconciliationResult,
        current_position: ExecutionPosition,
        events,
    ) -> RecoveryResult:
        """Run the complete self-healing workflow for one reconciliation."""
        reconciliation_id = reconciliation.id or "REC-UNKNOWN"

        self._advance(ReconciliationLifecycle.RUNNING)

        result = self._compare(reconciliation, current_position, events)

        if result.status == ReconciliationStatus.MATCHED:
            return self._matched(reconciliation_id)

        self._advance(ReconciliationLifecycle.MISMATCHED)
        self._metrics.record_reconciliation(matched=False)

        plan = self._planner.plan(result)

        if plan.action == RepairActionType.MANUAL_REVIEW:
            return self._manual_review(reconciliation_id, plan.reason)

        if not self._policy.can_auto_repair(plan):
            return self._manual_review(
                reconciliation_id,
                f"Repair action {plan.action.value} is not auto-repairable",
            )

        try:
            self._safety_guard.validate(plan, attempt=1)
        except RecoverySafetyError as exc:
            return self._manual_review(reconciliation_id, str(exc))

        self._advance(ReconciliationLifecycle.REPAIR_PLANNED)
        self._advance(ReconciliationLifecycle.REPAIRING)

        repair_result = self._repair_executor.execute(
            plan=plan,
            events=events,
            current_position=current_position,
            reconciliation_id=reconciliation_id,
        )
        self._metrics.record_repair(success=repair_result.success)

        if not repair_result.success:
            return self._failed(reconciliation_id, repair_result)

        verification = self._verify(
            events=events,
            rebuilt=repair_result.rebuilt_position,
        )
        self._complete_verification(repair_result, verification)

        self._advance(ReconciliationLifecycle.VERIFYING)

        if verification.verified:
            self._advance(ReconciliationLifecycle.RECOVERED)
            self._metrics.record_recovery(success=True)
            return RecoveryResult(
                reconciliation_id=reconciliation_id,
                lifecycle=ReconciliationLifecycle.RECOVERED,
                repaired=True,
                verified=True,
                repair_id=repair_result.repair_id,
                reason="Recovered after verified repair",
            )

        self._metrics.record_recovery(success=False)
        self._advance(ReconciliationLifecycle.MANUAL_REVIEW)
        return RecoveryResult(
            reconciliation_id=reconciliation_id,
            lifecycle=ReconciliationLifecycle.MANUAL_REVIEW,
            repaired=True,
            verified=False,
            repair_id=repair_result.repair_id,
            reason=verification.reason,
        )

    def _compare(
        self,
        reconciliation: ReconciliationResult,
        current_position: ExecutionPosition,
        events,
    ) -> ReconciliationResult:
        expected = self._position_builder.build(events)
        result = self._comparator.compare(
            expected=expected,
            actual=self._to_snapshot(current_position),
        )
        return replace(result, id=reconciliation.id)

    def _matched(self, reconciliation_id: str) -> RecoveryResult:
        self._advance(ReconciliationLifecycle.MATCHED)
        self._metrics.record_reconciliation(matched=True)
        return RecoveryResult(
            reconciliation_id=reconciliation_id,
            lifecycle=ReconciliationLifecycle.MATCHED,
            repaired=False,
            verified=True,
            repair_id=None,
            reason="Reconciliation matched; no repair required",
        )

    def _manual_review(self, reconciliation_id: str, reason: str) -> RecoveryResult:
        self._metrics.record_manual_review()
        self._advance(ReconciliationLifecycle.MANUAL_REVIEW)
        return RecoveryResult(
            reconciliation_id=reconciliation_id,
            lifecycle=ReconciliationLifecycle.MANUAL_REVIEW,
            repaired=False,
            verified=False,
            repair_id=None,
            reason=reason,
        )

    def _failed(
        self,
        reconciliation_id: str,
        repair_result: RepairResult,
    ) -> RecoveryResult:
        self._metrics.record_recovery(success=False)
        self._advance(ReconciliationLifecycle.FAILED)
        return RecoveryResult(
            reconciliation_id=reconciliation_id,
            lifecycle=ReconciliationLifecycle.FAILED,
            repaired=False,
            verified=False,
            repair_id=repair_result.repair_id,
            reason=repair_result.reason,
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

    def _advance(
        self,
        target: Lifecycle,
    ) -> None:
        self._lifecycle.advance(target)

    @staticmethod
    def _to_snapshot(position: ExecutionPosition) -> PositionSnapshot:
        return PositionSnapshot(
            symbol=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price,
            realized_pnl=position.realized_pnl,
        )

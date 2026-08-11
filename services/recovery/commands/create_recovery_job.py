"""CreateRecoveryJob — generates a recovery plan from a consistency check trigger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


# Lazy imports to avoid circular references at module load
def _consistency_check_from_dict(data: Dict[str, Any]):
    from services.consistency.domain.consistency_check import ConsistencyCheck, ExecutionFact
    return ConsistencyCheck.from_dict(data)


@dataclass
class CreateRecoveryJob:
    """Command: create a recovery job from a consistency check / trigger.

    Generates a RecoveryPlan based on what the consistency check found.
    """

    trigger_id: str
    check_id: str
    failure_type: str
    expected_value: Any = None
    actual_value: Any = None
    delta: Any = None
    account_id: Optional[str] = None
    instrument_id: Optional[str] = None
    execution_id: Optional[str] = None
    order_id: Optional[str] = None

    # ---- result ----
    job: Optional[Any] = None  # RecoveryJob — set after execute

    def execute(self, repository: Any, next_job_id: str) -> Any:
        """Execute the command: create job, generate plan, store via repository.

        Returns the created RecoveryJob.
        """
        from services.recovery.domain.recovery_job import (
            RecoveryJob,
            RecoveryPlan,
        )
        from services.recovery.domain.recovery_scope import (
            RecoveryScope,
            RecoveryScopeType,
        )
        from services.recovery.domain.recovery_status import RecoveryType

        # 1. Determine scope
        scope = self._determine_scope()

        # 2. Determine recovery type
        recovery_type = self._determine_recovery_type()

        # 3. Build recovery plan
        plan = self._build_plan(recovery_type)

        # 4. Create job
        self.job = RecoveryJob(
            job_id=next_job_id,
            recovery_type=recovery_type,
            scope=scope,
            source_check_id=self.check_id,
            plan=plan,
        )

        # 5. Persist
        repository.save(self.job)

        return self.job

    def _determine_scope(self):
        from services.recovery.domain.recovery_scope import (
            RecoveryScope,
            RecoveryScopeType,
        )

        if self.execution_id:
            return RecoveryScope.for_execution(
                execution_id=self.execution_id,
                account_id=self.account_id or "",
                instrument_id=self.instrument_id or "",
            )
        if self.order_id:
            return RecoveryScope.for_order(
                order_id=self.order_id,
                account_id=self.account_id or "",
                instrument_id=self.instrument_id or "",
            )
        if self.instrument_id:
            return RecoveryScope.for_instrument(
                account_id=self.account_id or "",
                instrument_id=self.instrument_id,
            )
        if self.account_id:
            return RecoveryScope.for_account(account_id=self.account_id)
        # Fallback
        return RecoveryScope(scope_type=RecoveryScopeType.ACCOUNT)

    def _determine_recovery_type(self):
        from services.recovery.domain.recovery_status import RecoveryType

        pos_patterns = {"POSITION_MISMATCH", "POSITION_OVERSTATE", "MISSING_POSITION_EVENT"}
        ledger_patterns = {
            "MISSING_LEDGER_ENTRY",
            "LEDGER_AMOUNT_MISMATCH",
            "MISSING_FEE_ENTRY",
            "COMMISSION_MISMATCH",
            "ACCOUNTING_IMBALANCE",
        }
        both_patterns = {"EVENT_SEQUENCE_GAP", "CROSS_DOMAIN_MISMATCH"}

        if self.failure_type in pos_patterns:
            return RecoveryType.POSITION_REPLAY
        if self.failure_type in ledger_patterns:
            return RecoveryType.LEDGER_REPLAY
        if self.failure_type in both_patterns:
            return RecoveryType.FULL_TRANSACTION_REPLAY
        return RecoveryType.FULL_TRANSACTION_REPLAY

    def _build_plan(self, recovery_type) -> Any:
        from services.recovery.domain.recovery_job import RecoveryPlan
        from services.recovery.domain.recovery_status import RecoveryType

        pos_action = "NO_ACTION"
        ledger_action = "NO_ACTION"
        proj_action = "NO_ACTION"

        if recovery_type == RecoveryType.POSITION_REPLAY:
            pos_action = "REPLAY_REQUIRED"
            proj_action = "REBUILD_REQUIRED"
        elif recovery_type == RecoveryType.LEDGER_REPLAY:
            ledger_action = "REPLAY_REQUIRED"
            proj_action = "REBUILD_REQUIRED"
        elif recovery_type == RecoveryType.FULL_TRANSACTION_REPLAY:
            pos_action = "REPLAY_REQUIRED"
            ledger_action = "REPLAY_REQUIRED"
            proj_action = "REBUILD_REQUIRED"
        elif recovery_type == RecoveryType.PROJECTION_REBUILD:
            proj_action = "REBUILD_REQUIRED"

        exec_ids = [self.execution_id] if self.execution_id else []

        return RecoveryPlan(
            source_execution_id=self.execution_id or "unknown",
            position_action=pos_action,
            ledger_action=ledger_action,
            projection_action=proj_action,
            reason=f"Triggered by {self.failure_type} (check {self.check_id})",
            execution_ids=exec_ids,
        )


def create_recovery_job(
    trigger_id: str,
    check_id: str,
    failure_type: str,
    repository: Any,
    next_job_id: str,
    **kwargs: Any,
) -> Any:
    """Convenience function to create and execute a CreateRecoveryJob command."""
    cmd = CreateRecoveryJob(
        trigger_id=trigger_id,
        check_id=check_id,
        failure_type=failure_type,
        **kwargs,
    )
    return cmd.execute(repository, next_job_id)

"""VerifyRecovery — post-recovery consistency verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class VerifyRecovery:
    """Command: verify that a recovery job produced consistent state.

    Runs cross-domain consistency checks against the replayed state and returns
    a verdict.
    """

    job: Any  # RecoveryJob
    position_view: Optional[Any] = None
    ledger_view: Optional[Any] = None
    execution_facts: List[Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.execution_facts is None:
            self.execution_facts = []

    def execute(self, consistency_service: Any) -> Dict[str, Any]:
        """Run post-recovery consistency verification."""
        from services.consistency.domain.consistency_check import ConsistencyCheck
        from services.consistency.domain.consistency_status import ConsistencyDomainStatus
        from services.recovery.domain.recovery_status import RecoveryType

        job = self.job

        results: Dict[str, Any] = {
            "consistent": True,
            "checks": {},
            "failure_code": None,
            "failure_reason": None,
        }

        # Run execution-position check if position was replayed
        if job.recovery_type in (
            RecoveryType.POSITION_REPLAY,
            RecoveryType.FULL_TRANSACTION_REPLAY,
        ):
            pos_check = consistency_service.check_execution(
                execution_id=self.execution_facts[0].execution_id
                if self.execution_facts
                else "",
                account_id=job.account_id or "",
                instrument_id=job.instrument_id or "",
            )
            results["checks"]["position"] = pos_check
            if pos_check.overall_status in (
                ConsistencyDomainStatus.INCONSISTENT,
                ConsistencyDomainStatus.DEGRADED,
            ):
                results["consistent"] = False
                results["failure_code"] = "POSITION_VERIFY_FAILED"
                results["failure_reason"] = (
                    f"Position still inconsistent after recovery: "
                    f"status={pos_check.overall_status.value}"
                )

        # Run execution-ledger check if ledger was replayed
        if job.recovery_type in (
            RecoveryType.LEDGER_REPLAY,
            RecoveryType.FULL_TRANSACTION_REPLAY,
        ):
            ledger_check = consistency_service.check_execution(
                execution_id=self.execution_facts[0].execution_id
                if self.execution_facts
                else "",
                account_id=job.account_id or "",
                instrument_id=job.instrument_id or "",
            )
            results["checks"]["ledger"] = ledger_check
            if ledger_check.overall_status in (
                ConsistencyDomainStatus.INCONSISTENT,
                ConsistencyDomainStatus.DEGRADED,
            ):
                results["consistent"] = False
                if not results["failure_code"]:
                    results["failure_code"] = "LEDGER_VERIFY_FAILED"
                    results["failure_reason"] = (
                        f"Ledger still inconsistent after recovery: "
                        f"status={ledger_check.overall_status.value}"
                    )

        return results


def verify_recovery(
    job: Any,
    consistency_service: Any,
    position_view: Optional[Any] = None,
    ledger_view: Optional[Any] = None,
    execution_facts: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Convenience function to verify recovery results."""
    cmd = VerifyRecovery(
        job=job,
        position_view=position_view,
        ledger_view=ledger_view,
        execution_facts=execution_facts or [],
    )
    return cmd.execute(consistency_service)

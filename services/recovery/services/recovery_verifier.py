"""RecoveryVerifier — post-recovery consistency verification service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RecoveryVerifier:
    """Verifies that recovery has restored consistency.

    Runs cross-domain checks and reports whether the system is back in a healthy state.
    """

    consistency_service: Any  # ConsistencyService

    def verify(self, job: Any, execution_facts: List[Any]) -> Dict[str, Any]:
        """Verify the recovered state is consistent.

        Returns:
            {
                "consistent": bool,
                "checks": { ... },
                "failure_code": str | None,
                "failure_reason": str | None,
            }
        """
        from services.consistency.domain.consistency_status import ConsistencyDomainStatus
        from services.recovery.domain.recovery_status import RecoveryType

        result: Dict[str, Any] = {
            "consistent": True,
            "checks": {},
            "failure_code": None,
            "failure_reason": None,
        }

        check = self.consistency_service.check_execution(
            execution_id=job.execution_id or "",
            account_id=job.account_id or "",
            instrument_id=job.instrument_id or "",
        )

        result["checks"]["cross_domain"] = check

        if check.overall_status == ConsistencyDomainStatus.CONSISTENT:
            result["consistent"] = True
        elif check.overall_status == ConsistencyDomainStatus.DEGRADED:
            result["consistent"] = True  # Grace period still counts as success
        else:
            result["consistent"] = False
            result["failure_code"] = "CONSISTENCY_VERIFY_FAILED"
            result["failure_reason"] = (
                f"Cross-domain check status: {check.overall_status.value}"
            )

        return result

    def verify_full(
        self,
        account_id: str,
        instrument_id: str,
    ) -> Dict[str, Any]:
        """Run full cross-domain verification for an account/instrument."""
        return self.verify(None, [])  # placeholder — uses service state

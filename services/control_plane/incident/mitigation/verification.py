"""
IncidentVerificationService — independent verification that mitigation worked.

An execution result is not the same as resolution: a mitigation may succeed
while the underlying problem persists. Verification is the last gate before
RESOLVED; a failed verification reopens the incident (spec section 17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..audit.event_type import IncidentAuditEventType
from ..incident_status import IncidentStateMachine, IncidentStatus


class VerificationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass
class VerificationResult:

    status: VerificationStatus

    checks: dict[str, Any]

    message: str = ""

    verified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class IncidentVerificationService:
    """Verifies control actions and, on failure, reopens the incident."""

    def __init__(self, audit_service: Any | None = None) -> None:
        self.audit_service = audit_service

    def verify(
        self,
        incident,
        checks: dict[str, Any],
        *,
        actor: str = "verification-engine",
        reopen_on_failure: bool = True,
    ) -> VerificationResult:
        if self.audit_service is not None:
            self.audit_service.record(
                incident.id,
                IncidentAuditEventType.VERIFICATION_STARTED,
                actor=actor,
                payload={"checks": list(checks)},
            )

        failed = [
            key
            for key, value in checks.items()
            if value is False
        ]

        if failed:
            result = VerificationResult(
                status=VerificationStatus.FAILED,
                checks=checks,
                message=(
                    "verification failed: "
                    + ", ".join(failed)
                ),
            )
            if self.audit_service is not None:
                self.audit_service.record(
                    incident.id,
                    IncidentAuditEventType.VERIFICATION_FAILED,
                    actor=actor,
                    payload={"failed_checks": failed},
                )
            if (
                reopen_on_failure
                and IncidentStateMachine.can_transition(
                    incident.status,
                    IncidentStatus.REOPENED,
                )
            ):
                incident.reopen(actor=actor)
            return result

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            message="all verification checks passed",
        )
        if self.audit_service is not None:
            self.audit_service.record(
                incident.id,
                IncidentAuditEventType.VERIFICATION_PASSED,
                actor=actor,
                payload={"checked": list(checks)},
            )
        return result

    def verify_and_resolve(
        self,
        incident,
        checks: dict[str, Any],
        *,
        resolution_reason: str,
        resolved_by: str,
        actor: str = "verification-engine",
    ) -> VerificationResult:
        """Verify first; resolve only when every check passes.

        This is the canonical recovery loop gate: a successful mitigation alone
        never resolves the incident — verification must pass first.
        """
        result = self.verify(
            incident,
            checks,
            actor=actor,
            reopen_on_failure=False,
        )
        if result.status is VerificationStatus.FAILED:
            return result
        incident.resolve(
            resolution_reason,
            resolved_by,
            verification_result=result.status.value,
        )
        return result

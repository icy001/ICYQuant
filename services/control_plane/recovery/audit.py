"""
Recovery audit — every recovery transition must produce an audit event
(Commit 26 Part 1.5, spec section 30):

    RECOVERY_VALIDATION_STARTED
    RECOVERY_VALIDATION_FAILED
    RECOVERY_VALIDATION_PASSED
    RECOVERY_APPROVAL_REQUIRED
    RECOVERY_APPROVED
    RECOVERY_RESUME_STARTED
    RECOVERY_COMPLETED
    RECOVERY_FAILED

Each event is correlated with incident_id / control_id / actor / reason /
timestamp / previous_state / new_state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .state import RecoveryState


class RecoveryAuditEventType(str, Enum):

    RECOVERY_VALIDATION_STARTED = "RECOVERY_VALIDATION_STARTED"

    RECOVERY_VALIDATION_FAILED = "RECOVERY_VALIDATION_FAILED"

    RECOVERY_VALIDATION_PASSED = "RECOVERY_VALIDATION_PASSED"

    RECOVERY_APPROVAL_REQUIRED = "RECOVERY_APPROVAL_REQUIRED"

    RECOVERY_APPROVED = "RECOVERY_APPROVED"

    RECOVERY_RESUME_STARTED = "RECOVERY_RESUME_STARTED"

    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"

    RECOVERY_FAILED = "RECOVERY_FAILED"


@dataclass(frozen=True)
class RecoveryAuditRecord:

    event_type: RecoveryAuditEventType

    previous_state: RecoveryState | None

    new_state: RecoveryState

    recovery_id: UUID | None = None

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    actor: str = "recovery-controller"

    reason: str = ""

    system_state: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

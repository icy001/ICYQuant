from __future__ import annotations

from enum import Enum


class RecoveryStatus(str, Enum):
    """State machine for a recovery job.

    DETECTED → CREATED → PRECHECKING → REPLAYING → VERIFYING → COMPLETED
                                          │              │
                                          └─ BLOCKED     └─ FAILED → (retry) PRECHECKING
                                                                   → ESCALATED
    """

    DETECTED = "DETECTED"
    CREATED = "CREATED"
    PRECHECKING = "PRECHECKING"
    BLOCKED = "BLOCKED"
    REPLAYING = "REPLAYING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    DEDUPLICATED = "DEDUPLICATED"

    @property
    def is_terminal(self) -> bool:
        """Return True for terminal states that will not transition further."""
        return self in (
            RecoveryStatus.COMPLETED,
            RecoveryStatus.BLOCKED,
            RecoveryStatus.ESCALATED,
            RecoveryStatus.DEDUPLICATED,
        )

    @property
    def is_active(self) -> bool:
        """Return True for in-progress states."""
        return self in (
            RecoveryStatus.CREATED,
            RecoveryStatus.PRECHECKING,
            RecoveryStatus.REPLAYING,
            RecoveryStatus.VERIFYING,
        )

    @property
    def can_retry(self) -> bool:
        """Return True if the job can be retried from this state."""
        return self in (RecoveryStatus.FAILED,)


class RecoveryType(str, Enum):
    """Type of recovery operation to perform."""

    POSITION_REPLAY = "POSITION_REPLAY"
    LEDGER_REPLAY = "LEDGER_REPLAY"
    FULL_TRANSACTION_REPLAY = "FULL_TRANSACTION_REPLAY"
    PROJECTION_REBUILD = "PROJECTION_REBUILD"

"""
Audit Outcome — standardized outcomes for governance audit events.
"""

from __future__ import annotations

from enum import Enum, auto


class AuditOutcome(Enum):
    """Standardized audit outcomes."""

    SUCCESS = auto()
    FAILURE = auto()
    PARTIAL = auto()
    PENDING = auto()
    TIMEOUT = auto()
    ERROR = auto()

    # Policy-specific
    POLICY_PASS = auto()
    POLICY_FAIL = auto()
    POLICY_WARNING = auto()

    # Authority-specific
    AUTHORITY_VALID = auto()
    AUTHORITY_INVALID = auto()
    AUTHORITY_EXPIRED = auto()
    AUTHORITY_EXCEEDED = auto()

    # Approval-specific
    APPROVAL_GRANTED = auto()
    APPROVAL_DENIED = auto()
    APPROVAL_EXPIRED = auto()
    APPROVAL_CONFLICT = auto()

    # Integrity
    INTEGRITY_VALID = auto()
    INTEGRITY_INVALID = auto()
    HASH_MISMATCH = auto()
    CHAIN_BROKEN = auto()

    @property
    def is_success(self) -> bool:
        return self in (
            AuditOutcome.SUCCESS,
            AuditOutcome.POLICY_PASS,
            AuditOutcome.AUTHORITY_VALID,
            AuditOutcome.APPROVAL_GRANTED,
            AuditOutcome.INTEGRITY_VALID,
        )

    @property
    def is_failure(self) -> bool:
        return not self.is_success and self != AuditOutcome.PENDING

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value}

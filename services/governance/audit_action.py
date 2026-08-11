"""
Audit Action — standardized actions for governance audit events.

Every audit event must be about a specific action, not just a generic "something happened".
"""

from __future__ import annotations

from enum import Enum, auto


class AuditAction(Enum):
    """Standardized governance audit actions."""

    # CRUD
    CREATE = auto()
    UPDATE = auto()
    DELETE = auto()

    # Validation
    VALIDATE = auto()
    REJECT = auto()

    # Approval
    SUBMIT = auto()
    APPROVE = auto()
    DENY = auto()

    # Lifecycle
    PUBLISH = auto()
    ACTIVATE = auto()
    DEACTIVATE = auto()
    REVOKE = auto()
    SUPERSEDE = auto()
    ARCHIVE = auto()
    EXPIRE = auto()
    CANCEL = auto()
    INVALIDATE = auto()

    # Execution
    EXECUTE = auto()
    FULFILL = auto()
    FAIL = auto()

    # Authority
    GRANT = auto()
    MODIFY_AUTHORITY = auto()
    REVOKE_AUTHORITY = auto()
    DELEGATE = auto()
    REVOKE_DELEGATION = auto()

    # Override
    OVERRIDE = auto()
    ROLLBACK = auto()

    # Audit
    VERIFY_INTEGRITY = auto()
    DETECT_TAMPER = auto()
    DETECT_ORPHAN = auto()
    DETECT_CONFLICT = auto()

    # Emergency
    EMERGENCY_ACTION = auto()

    # Query
    QUERY = auto()
    REPLAY = auto()
    RECONSTRUCT = auto()

    @property
    def is_mutating(self) -> bool:
        """Whether this action changes state."""
        return self not in (AuditAction.QUERY, AuditAction.REPLAY)

    @property
    def is_destructive(self) -> bool:
        """Whether this action is destructive/non-reversible."""
        return self in (
            AuditAction.DELETE,
            AuditAction.REVOKE,
            AuditAction.REVOKE_AUTHORITY,
            AuditAction.REVOKE_DELEGATION,
            AuditAction.EMERGENCY_ACTION,
        )

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value}

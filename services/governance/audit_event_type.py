"""
Audit Event Type — unified enumeration of all governance audit events.

Every audit event across the entire governance system is categorized
under a single, flat enumeration for consistent querying and lineage.
"""

from __future__ import annotations

from enum import Enum, auto


class AuditEventType(Enum):
    """Unified audit event type covering all governance domains."""

    # ── Decision Lifecycle ──
    DECISION_CREATED = auto()
    DECISION_UPDATED = auto()
    DECISION_APPROVED = auto()
    DECISION_REJECTED = auto()
    DECISION_INVALIDATED = auto()
    DECISION_EXPIRED = auto()
    DECISION_CANCELLED = auto()
    DECISION_OVERRIDDEN = auto()
    DECISION_EXECUTED = auto()

    # ── Policy Lifecycle ──
    POLICY_CREATED = auto()
    POLICY_UPDATED = auto()
    POLICY_VALIDATED = auto()
    POLICY_PUBLISHED = auto()
    POLICY_ACTIVATED = auto()
    POLICY_REVOKED = auto()
    POLICY_ROLLED_BACK = auto()
    POLICY_EXPIRED = auto()
    POLICY_DELETED = auto()

    # ── Authority Lifecycle ──
    AUTHORITY_GRANTED = auto()
    AUTHORITY_MODIFIED = auto()
    AUTHORITY_REVOKED = auto()
    AUTHORITY_EXPIRED = auto()
    AUTHORITY_DENIED = auto()

    # ── Delegation Lifecycle ──
    DELEGATION_CREATED = auto()
    DELEGATION_REVOKED = auto()
    DELEGATION_EXPIRED = auto()
    DELEGATION_APPLIED = auto()
    DELEGATION_EXCEEDED = auto()

    # ── Approval Lifecycle ──
    APPROVAL_CREATED = auto()
    APPROVAL_SUBMITTED = auto()
    APPROVAL_APPROVED = auto()
    APPROVAL_REJECTED = auto()
    APPROVAL_EXPIRED = auto()
    APPROVAL_CANCELLED = auto()
    APPROVAL_INVALIDATED = auto()
    APPROVAL_OVERRIDDEN = auto()

    # ── Order Lifecycle ──
    ORDER_CREATED = auto()
    ORDER_UPDATED = auto()
    ORDER_APPROVED = auto()
    ORDER_REJECTED = auto()
    ORDER_SUBMITTED = auto()
    ORDER_CANCELLED = auto()

    # ── Execution Lifecycle ──
    EXECUTION_STARTED = auto()
    EXECUTION_COMPLETED = auto()
    EXECUTION_FAILED = auto()
    EXECUTION_CANCELLED = auto()
    EXECUTION_PARTIAL = auto()

    # ── Audit Integrity ──
    AUDIT_INTEGRITY_FAILURE = auto()
    AUDIT_HASH_MISMATCH = auto()
    AUDIT_CHAIN_BROKEN = auto()
    AUDIT_ORPHAN_DETECTED = auto()
    AUDIT_LINEAGE_CONFLICT = auto()
    AUDIT_INCOMPLETE_LINEAGE = auto()

    # ── Emergency ──
    EMERGENCY_OVERRIDE_APPLIED = auto()
    EMERGENCY_CONTROLLER_ACTION = auto()

    # ── Human Interaction ──
    HUMAN_OVERRIDE_CREATED = auto()
    HUMAN_OVERRIDE_APPROVED = auto()
    HUMAN_OVERRIDE_REJECTED = auto()

    # ── System ──
    GOVERNANCE_ERROR = auto()
    SYSTEM_EVENT = auto()

    # ── Classification helpers ──

    @property
    def domain(self) -> str:
        """Return the governance domain of this event."""
        prefix = self.name.split("_")[0]
        return prefix

    @property
    def is_decision_event(self) -> bool:
        return self.name.startswith("DECISION_")

    @property
    def is_policy_event(self) -> bool:
        return self.name.startswith("POLICY_")

    @property
    def is_authority_event(self) -> bool:
        return self.name.startswith("AUTHORITY_")

    @property
    def is_approval_event(self) -> bool:
        return self.name.startswith("APPROVAL_")

    @property
    def is_execution_event(self) -> bool:
        return self.name.startswith("EXECUTION_")

    @property
    def is_audit_integrity_event(self) -> bool:
        return self.name.startswith("AUDIT_")

    @property
    def is_terminal(self) -> bool:
        """Events that represent a final state."""
        return self in (
            AuditEventType.DECISION_APPROVED,
            AuditEventType.DECISION_REJECTED,
            AuditEventType.DECISION_EXPIRED,
            AuditEventType.DECISION_CANCELLED,
            AuditEventType.DECISION_EXECUTED,
            AuditEventType.APPROVAL_APPROVED,
            AuditEventType.APPROVAL_REJECTED,
            AuditEventType.APPROVAL_EXPIRED,
            AuditEventType.APPROVAL_CANCELLED,
            AuditEventType.EXECUTION_COMPLETED,
            AuditEventType.EXECUTION_FAILED,
        )

    @property
    def is_critical(self) -> bool:
        """Events that require guaranteed audit persistence."""
        return self in (
            AuditEventType.POLICY_PUBLISHED,
            AuditEventType.POLICY_ACTIVATED,
            AuditEventType.POLICY_REVOKED,
            AuditEventType.POLICY_ROLLED_BACK,
            AuditEventType.AUTHORITY_GRANTED,
            AuditEventType.AUTHORITY_REVOKED,
            AuditEventType.APPROVAL_APPROVED,
            AuditEventType.APPROVAL_REJECTED,
            AuditEventType.HUMAN_OVERRIDE_APPROVED,
            AuditEventType.EMERGENCY_OVERRIDE_APPLIED,
            AuditEventType.AUDIT_INTEGRITY_FAILURE,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "is_terminal": self.is_terminal,
            "is_critical": self.is_critical,
        }

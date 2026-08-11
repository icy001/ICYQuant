"""
Governance Event — domain events for the governance subsystem.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class GovernanceEventType(Enum):
    """Event types emitted by the governance subsystem."""

    # Decision lifecycle
    GOVERNANCE_DECISION_REQUESTED = auto()
    GOVERNANCE_POLICY_EVALUATED = auto()
    GOVERNANCE_AUTHORITY_EVALUATED = auto()
    GOVERNANCE_CONSTRAINT_CHECKED = auto()
    GOVERNANCE_APPROVAL_REQUIRED = auto()
    GOVERNANCE_APPROVED = auto()
    GOVERNANCE_REJECTED = auto()
    GOVERNANCE_BLOCKED = auto()
    GOVERNANCE_OVERRIDE = auto()
    GOVERNANCE_EXECUTED = auto()

    # Policy events
    POLICY_REGISTERED = auto()
    POLICY_UPDATED = auto()
    POLICY_REMOVED = auto()
    POLICY_BREACH = auto()

    # Versioned policy events (Commit 20 Part 1.2)
    POLICY_VERSION_CREATED = auto()
    POLICY_VERSION_VALIDATED = auto()
    POLICY_VERSION_APPROVED = auto()
    POLICY_VERSION_PUBLISHED = auto()
    POLICY_VERSION_ACTIVATED = auto()
    POLICY_VERSION_SUPERSEDED = auto()
    POLICY_VERSION_ARCHIVED = auto()
    POLICY_VERSION_REJECTED = auto()
    POLICY_VERSION_REVOKED = auto()
    POLICY_VERSION_EXPIRED = auto()
    POLICY_CONFLICT_DETECTED = auto()
    POLICY_DEPENDENCY_VIOLATION = auto()
    POLICY_CHECKSUM_FAILURE = auto()
    POLICY_OVERRIDE_CREATED = auto()
    POLICY_OVERRIDE_APPLIED = auto()

    # Authority events
    AUTHORITY_GRANTED = auto()
    AUTHORITY_REVOKED = auto()
    AUTHORITY_DENIED = auto()

    # Constraint events
    CONSTRAINT_PASSED = auto()
    CONSTRAINT_FAILED = auto()

    # Approval events
    APPROVAL_REQUESTED = auto()
    APPROVAL_GRANTED = auto()
    APPROVAL_DENIED = auto()
    APPROVAL_EXPIRED = auto()

    # Approval detail events (Part 1.3)
    APPROVAL_CREATED = auto()
    APPROVAL_SUBMITTED = auto()
    APPROVAL_STATUS_TRANSITION = auto()
    APPROVAL_INVALIDATED = auto()
    APPROVAL_CANCELLED = auto()
    APPROVAL_REVOKED = auto()
    APPROVAL_REPLAY_DETECTED = auto()
    APPROVAL_SCOPE_MISMATCH = auto()
    APPROVAL_AMOUNT_EXCEEDED = auto()
    APPROVAL_MATERIAL_CHANGE = auto()
    APPROVAL_REVALIDATED = auto()

    # Delegation events (Part 1.3)
    DELEGATION_CREATED = auto()
    DELEGATION_ACTIVATED = auto()
    DELEGATION_REVOKED = auto()
    DELEGATION_EXPIRED = auto()
    DELEGATION_VALIDATION_FAILED = auto()
    DELEGATION_LIMIT_EXCEEDED = auto()
    DELEGATION_DEPTH_EXCEEDED = auto()

    # Authority detail events (Part 1.3)
    AUTHORITY_MODIFIED = auto()
    AUTHORITY_EXPIRED = auto()
    AUTHORITY_SUSPENDED = auto()
    AUTHORITY_RESTORED = auto()
    AUTHORITY_SCOPE_VIOLATION = auto()

    # System
    GOVERNANCE_ERROR = auto()

    # Audit & Lineage events (Commit 20 Part 1.4)
    AUDIT_EVENT_RECORDED = auto()
    AUDIT_INTEGRITY_FAILURE = auto()
    AUDIT_HASH_MISMATCH = auto()
    AUDIT_CHAIN_BROKEN = auto()
    AUDIT_ORPHAN_DETECTED = auto()
    LINEAGE_NODE_ADDED = auto()
    LINEAGE_EDGE_ADDED = auto()
    LINEAGE_SNAPSHOT_CAPTURED = auto()
    LINEAGE_CONFLICT_DETECTED = auto()
    DECISION_REPLAYED = auto()
    DECISION_REPLAY_MISMATCH = auto()
    HUMAN_OVERRIDE_CREATED = auto()
    HUMAN_OVERRIDE_APPLIED = auto()
    EMERGENCY_OVERRIDE_APPLIED = auto()

    # Autonomous Governance Control Plane (Commit 20 Part 1.5)
    GOVERNANCE_STATE_TRANSITION = auto()
    GOVERNANCE_CONTROL_DECISION = auto()
    GOVERNANCE_INTERVENTION_EXECUTED = auto()
    GOVERNANCE_INTERVENTION_FAILED = auto()
    GOVERNANCE_FREEZE_APPLIED = auto()
    GOVERNANCE_FREEZE_REMOVED = auto()
    GOVERNANCE_EXPOSURE_REDUCED = auto()
    GOVERNANCE_AUTHORITY_REVOKED = auto()
    GOVERNANCE_ESCALATED = auto()
    GOVERNANCE_EMERGENCY_ACTIVATED = auto()
    GOVERNANCE_EMERGENCY_RESOLVED = auto()
    GOVERNANCE_RECOVERY_STARTED = auto()
    GOVERNANCE_RECOVERY_COMPLETED = auto()
    GOVERNANCE_WATCHDOG_ALERT = auto()
    GOVERNANCE_WATCHDOG_FAILURE = auto()
    GOVERNANCE_CONTROL_LOOP_CYCLE = auto()


@dataclass
class GovernanceEvent:
    """A single governance event.

    Part 1.4: now includes correlation_id and causation_id
    for full audit lineage tracing.
    """

    event_id: str = field(default_factory=lambda: f"GEVT-{uuid.uuid4().hex[:12]}")
    event_type: GovernanceEventType = GovernanceEventType.GOVERNANCE_ERROR

    # Correlation
    decision_id: str = ""
    request_id: str = ""

    # Lineage tracing (Part 1.4)
    correlation_id: str = ""
    causation_id: str = ""

    # Metadata
    actor: str = ""
    decision_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)

    @property
    def is_error(self) -> bool:
        return self.event_type == GovernanceEventType.GOVERNANCE_ERROR

    @property
    def is_terminal(self) -> bool:
        return self.event_type in (
            GovernanceEventType.GOVERNANCE_APPROVED,
            GovernanceEventType.GOVERNANCE_REJECTED,
            GovernanceEventType.GOVERNANCE_BLOCKED,
            GovernanceEventType.GOVERNANCE_EXECUTED,
            GovernanceEventType.GOVERNANCE_OVERRIDE,
            GovernanceEventType.GOVERNANCE_ERROR,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "actor": self.actor,
            "decision_type": self.decision_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "is_error": self.is_error,
            "is_terminal": self.is_terminal,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GovernanceEvent":
        return cls(
            event_id=data.get("event_id", ""),
            event_type=GovernanceEventType[data.get("event_type", "GOVERNANCE_ERROR")],
            decision_id=data.get("decision_id", ""),
            request_id=data.get("request_id", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            actor=data.get("actor", ""),
            decision_type=data.get("decision_type", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
        )

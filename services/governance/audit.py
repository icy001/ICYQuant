"""Audit — immutable governance audit evidence (Commit 28 Part 1.1/1.3/1.5).

Governance Audit 回答"谁被允许做了什么？为什么允许？依据什么 Policy？
有没有 Approval？"，与 Incident Audit（事故发生了什么）职责不同，
两者最终通过 incident_id 关联。

Part 1.3 adds approval audit events: every Approval state change must be
recorded (APPROVAL_CREATED / APPROVAL_APPROVED / APPROVAL_REJECTED /
APPROVAL_EXPIRED / APPROVAL_CONSUMED / APPROVAL_DENIED) so the full
Request -> Approved -> Consumed chain is traceable.

Part 1.5 adds governance decision audit events: the Decision Ledger emits
GOVERNANCE_DECISION_CREATED / ALLOWED / DENIED / APPROVAL_REQUIRED, the
Replayer emits GOVERNANCE_DECISION_REPLAYED / REPLAY_MISMATCH, evidence
creation emits GOVERNANCE_EVIDENCE_CREATED and chain validation emits
GOVERNANCE_CHAIN_VALIDATED / GOVERNANCE_CHAIN_INVALID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .decision import DecisionEffect


class GovernanceAuditEventType(str, Enum):
    """Types of governance decision / ledger audit events (Part 1.5)."""

    GOVERNANCE_DECISION_CREATED = "GOVERNANCE_DECISION_CREATED"
    GOVERNANCE_DECISION_ALLOWED = "GOVERNANCE_DECISION_ALLOWED"
    GOVERNANCE_DECISION_DENIED = "GOVERNANCE_DECISION_DENIED"
    GOVERNANCE_APPROVAL_REQUIRED = "GOVERNANCE_APPROVAL_REQUIRED"
    GOVERNANCE_DECISION_REPLAYED = "GOVERNANCE_DECISION_REPLAYED"
    GOVERNANCE_DECISION_REPLAY_MISMATCH = "GOVERNANCE_DECISION_REPLAY_MISMATCH"
    GOVERNANCE_EVIDENCE_CREATED = "GOVERNANCE_EVIDENCE_CREATED"
    GOVERNANCE_CHAIN_VALIDATED = "GOVERNANCE_CHAIN_VALIDATED"
    GOVERNANCE_CHAIN_INVALID = "GOVERNANCE_CHAIN_INVALID"


@dataclass(frozen=True)
class GovernanceAuditEvent:
    """An immutable record of a governance decision."""

    event_id: str
    timestamp: datetime
    principal_id: str
    resource: str
    action: str
    effect: str
    reason: str
    policy_id: str | None = None
    incident_id: str | None = None
    approval_id: str | None = None
    # Commit 28 Part 1.5 — decision ledger / evidence linkage
    event_type: GovernanceAuditEventType | None = None
    decision_id: str | None = None
    reason_code: str | None = None


def decision_to_audit_event(
    decision,
    event_type: GovernanceAuditEventType,
    event_id: str | None = None,
    incident_id: str | None = None,
) -> GovernanceAuditEvent:
    """Build an audit event from a ledger decision (Commit 28 Part 1.5).

    ``decision`` may be a :class:`GovernanceDecision` or a
    :class:`GovernanceEvidence` (replay / evidence audit records); the
    relevant attributes are read defensively with ``getattr``.
    """
    effect = getattr(decision, "effect", None)
    if isinstance(effect, DecisionEffect):
        effect = effect.value
    timestamp = (
        getattr(decision, "decided_at", None)
        or getattr(decision, "created_at", None)
        or datetime.now(timezone.utc)
    )
    return GovernanceAuditEvent(
        event_id=event_id or f"AUD-{uuid.uuid4().hex[:12]}",
        timestamp=timestamp,
        principal_id=getattr(decision, "principal_id", None) or "",
        resource=getattr(decision, "resource", None) or "",
        action=getattr(decision, "action", None) or "",
        effect=str(effect or "UNKNOWN"),
        reason=getattr(decision, "reason", None) or "",
        policy_id=getattr(decision, "policy_id", None),
        incident_id=incident_id,
        approval_id=getattr(decision, "approval_id", None),
        event_type=event_type,
        decision_id=getattr(decision, "decision_id", None),
        reason_code=getattr(decision, "reason_code", None),
    )


class GovernanceAuditStore:
    """Append-only store of governance decision audit events (Part 1.5)."""

    def __init__(self) -> None:
        self._events: list[GovernanceAuditEvent] = []

    def record(self, event: GovernanceAuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[GovernanceAuditEvent, ...]:
        return tuple(self._events)

    def for_decision(self, decision_id: str) -> tuple[GovernanceAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.decision_id == decision_id
        )

    def for_type(
        self, event_type: GovernanceAuditEventType
    ) -> tuple[GovernanceAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.event_type == event_type
        )

    def for_principal(self, principal_id: str) -> tuple[GovernanceAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.principal_id == principal_id
        )


class ApprovalAuditEventType(str, Enum):
    """Types of approval lifecycle audit events."""

    APPROVAL_CREATED = "APPROVAL_CREATED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_CONSUMED = "APPROVAL_CONSUMED"
    APPROVAL_DENIED = "APPROVAL_DENIED"


@dataclass(frozen=True)
class ApprovalAuditEvent:
    """An immutable record of an approval state change."""

    event_id: str
    event_type: ApprovalAuditEventType
    timestamp: datetime
    approval_id: str
    resource: str
    action: str
    requester: str
    actor: str | None = None
    incident_id: str | None = None
    reason: str | None = None


class ApprovalAuditStore:
    """Append-only store of approval audit events."""

    def __init__(self) -> None:
        self._events: list[ApprovalAuditEvent] = []

    def record(self, event: ApprovalAuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[ApprovalAuditEvent, ...]:
        return tuple(self._events)

    def for_approval(self, approval_id: str) -> tuple[ApprovalAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.approval_id == approval_id
        )

    def for_incident(self, incident_id: str) -> tuple[ApprovalAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.incident_id == incident_id
        )

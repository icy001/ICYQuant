"""Audit — immutable governance audit evidence (Commit 28 Part 1.1, Part 1.3).

Governance Audit 回答"谁被允许做了什么？为什么允许？依据什么 Policy？
有没有 Approval？"，与 Incident Audit（事故发生了什么）职责不同，
两者最终通过 incident_id 关联。

Part 1.3 adds approval audit events: every Approval state change must be
recorded (APPROVAL_CREATED / APPROVAL_APPROVED / APPROVAL_REJECTED /
APPROVAL_EXPIRED / APPROVAL_CONSUMED / APPROVAL_DENIED) so the full
Request -> Approved -> Consumed chain is traceable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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

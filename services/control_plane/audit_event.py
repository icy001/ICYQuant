"""Typed audit event with a tamper-evident hash chain (Commit 29 Part 1.5 §4-8, §43-45).

Audit events answer *who did what, in which context, and why* - the
responsibility layer of observability, strictly separated from the factual
``ControlEvent`` stream (§4).

Each audit event is chained to its predecessor:

    Event #1 -> hash -> Event #2 -> hash -> Event #3 ...

Any modification to a past event breaks the chain and is detected by
``verify_audit_chain`` (AUDIT_INTEGRITY_FAILURE, §45).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence


class AuditEventType(str):
    """Typed audit event types (§11 / §54-57)."""

    COMMAND_CREATED = "COMMAND_CREATED"
    COMMAND_RECEIVED = "COMMAND_RECEIVED"
    AUTHORIZATION_STARTED = "AUTHORIZATION_STARTED"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    COMMAND_DISPATCHED = "COMMAND_DISPATCHED"
    EXECUTION_CLAIMED = "EXECUTION_CLAIMED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    COMMAND_UNKNOWN = "COMMAND_UNKNOWN"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    TARGET_RECONCILED = "TARGET_RECONCILED"
    COMMAND_SUCCEEDED = "COMMAND_SUCCEEDED"
    COMMAND_FAILED = "COMMAND_FAILED"
    COMMAND_CANCELLED = "COMMAND_CANCELLED"
    DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    REPLAY_REJECTED = "REPLAY_REJECTED"


@dataclass(frozen=True)
class AuditEvent:
    """A single immutable audit event (§5 + hash chain fields §43)."""

    audit_id: str
    event_type: str
    command_id: str
    principal_id: str
    action: str
    resource: str
    target: str
    decision: str
    reason: str
    timestamp: datetime
    correlation_id: str
    causation_id: str | None
    sequence: int
    previous_event_hash: str | None = None
    event_hash: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class AuditIntegrityError(Exception):
    """The audit chain is broken: hash, previous-hash or sequence mismatch (§45)."""


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def calculate_event_hash(event: AuditEvent) -> str:
    """SHA-256 over the canonical audit payload (§44, extended for §57).

    The hash covers the identity/type/command/sequence/timestamp/previous-link
    fields from §44 *plus* the responsibility fields (principal, action,
    resource, target, decision, reason, detail). Any modification of a past
    event - including its ``reason`` - therefore breaks the chain and is
    detected by :func:`verify_audit_chain` (§57). The stored ``event_hash``
    itself is not part of its own input, so it can always be recomputed.
    """
    payload = {
        "event_id": event.audit_id,
        "event_type": event.event_type,
        "command_id": event.command_id,
        "sequence": event.sequence,
        "timestamp": event.timestamp.isoformat(),
        "previous_event_hash": event.previous_event_hash,
        "principal_id": event.principal_id,
        "action": event.action,
        "resource": event.resource,
        "target": event.target,
        "decision": event.decision,
        "reason": event.reason,
        "detail": event.detail,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def verify_audit_chain(events: Sequence[AuditEvent]) -> bool:
    """Verify sequence, hash and previous-hash consistency (§45).

    Returns ``True`` for a valid chain; any mismatch (including a missing
    link) means the audit evidence chain may have been tampered with.
    """
    ordered = sorted(events, key=lambda event: event.sequence)
    if not ordered:
        return True

    previous_hash: str | None = None
    for index, event in enumerate(ordered):
        if index > 0 and ordered[index - 1].sequence + 1 != event.sequence:
            return False
        if event.event_hash != calculate_event_hash(event):
            return False
        if event.previous_event_hash != previous_hash:
            return False
        previous_hash = event.event_hash
    return True


class AuditTrail:
    """Append-only, tamper-evident audit trail (§5, §43).

    Every recorded event is automatically chained to the previous one with a
    SHA-256 hash. Events are never mutated after append.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._sequence = 0

    def record(
        self,
        *,
        event_type: str,
        command_id: str,
        principal_id: str,
        action: str,
        resource: str,
        target: str,
        decision: str,
        reason: str,
        correlation_id: str,
        causation_id: str | None = None,
        timestamp: datetime | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        self._sequence += 1
        previous_hash = self._events[-1].event_hash if self._events else None
        event = AuditEvent(
            audit_id=f"AUD-{self._sequence:04d}",
            event_type=event_type,
            command_id=command_id,
            principal_id=principal_id,
            action=action,
            resource=resource,
            target=target,
            decision=decision,
            reason=reason,
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            causation_id=causation_id,
            sequence=self._sequence,
            previous_event_hash=previous_hash,
            event_hash="",  # placeholder, replaced below
            detail=dict(detail or {}),
        )
        computed = calculate_event_hash(event)
        # Rebuild with the real hash; event_hash is not part of its own input.
        event = AuditEvent(
            audit_id=event.audit_id,
            event_type=event.event_type,
            command_id=event.command_id,
            principal_id=event.principal_id,
            action=event.action,
            resource=event.resource,
            target=event.target,
            decision=event.decision,
            reason=event.reason,
            timestamp=event.timestamp,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            sequence=event.sequence,
            previous_event_hash=event.previous_event_hash,
            event_hash=computed,
            detail=event.detail,
        )
        self._events.append(event)
        return event

    def events(self, command_id: str | None = None) -> tuple[AuditEvent, ...]:
        if command_id is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.command_id == command_id)

    def by_correlation_id(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        return tuple(event for event in self._events if event.correlation_id == correlation_id)

    def verify(self) -> bool:
        """Verify the whole stored chain (§56)."""
        return verify_audit_chain(self._events)

    def __len__(self) -> int:
        return len(self._events)

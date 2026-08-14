"""Control authorization audit trail (Commit 29 Part 1.2 §24-26).

Every authorization step emits a typed audit event. All events for one
control chain share the same ``correlation_id`` so the full path

    REQUESTED -> AUTHORIZATION_REQUESTED -> ... -> EXECUTION_SUCCEEDED

can be rebuilt from a single ID (§26).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ControlAuditEventType(str, Enum):
    """Typed control-plane audit events (§24)."""

    AUTHORIZATION_REQUESTED = "CONTROL_AUTHORIZATION_REQUESTED"
    AUTHORIZATION_GRANTED = "CONTROL_AUTHORIZATION_GRANTED"
    AUTHORIZATION_DENIED = "CONTROL_AUTHORIZATION_DENIED"
    APPROVAL_REQUIRED = "CONTROL_APPROVAL_REQUIRED"
    AUTHORIZATION_GRANT_CREATED = "CONTROL_AUTHORIZATION_GRANT_CREATED"
    EXECUTION_STARTED = "CONTROL_EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "CONTROL_EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "CONTROL_EXECUTION_FAILED"


@dataclass(frozen=True)
class ControlAuditEvent:
    """A single immutable audit event (§24-25)."""

    event_id: int
    event_type: ControlAuditEventType
    correlation_id: str
    request_id: str
    command_id: str
    occurred_at: datetime
    detail: dict[str, Any] | None = None


class ControlAuditLog:
    """In-memory append-only audit log (§24).

    Events are only appended, never mutated, so the audit chain is
    trustworthy within the process lifetime. A production adapter would
    persist these records; the interface is identical.
    """

    def __init__(self) -> None:
        self._events: list[ControlAuditEvent] = []
        self._sequence = 0

    def record(
        self,
        event_type: ControlAuditEventType,
        *,
        correlation_id: str,
        request_id: str,
        command_id: str,
        detail: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> ControlAuditEvent:
        self._sequence += 1
        event = ControlAuditEvent(
            event_id=self._sequence,
            event_type=event_type,
            correlation_id=correlation_id,
            request_id=request_id,
            command_id=command_id,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            detail=detail,
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[ControlAuditEvent, ...]:
        return tuple(self._events)

    def by_correlation_id(self, correlation_id: str) -> tuple[ControlAuditEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.correlation_id == correlation_id
        )

    def by_command_id(self, command_id: str) -> tuple[ControlAuditEvent, ...]:
        return tuple(
            event for event in self._events if event.command_id == command_id
        )

    def has(self, event_type: ControlAuditEventType) -> bool:
        return any(event.event_type is event_type for event in self._events)

    def __len__(self) -> int:
        return len(self._events)

"""Control event model and in-memory event store (Commit 29 Part 1.5 §9-11).

Events are the *fact* layer of observability: they describe what happened
(COMMAND_CREATED, EXECUTION_TIMEOUT, ...). They are distinct from audit
events, which carry responsibility and context (§4).

Every event belongs to a command and carries:

    correlation_id  - groups the whole control chain of one incident
    causation_id    - the event_id of the event that caused this one
    sequence        - per-command ordering that survives out-of-order delivery
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ControlEventType(str):
    """Typed control events (§11). Values are stable strings used in sinks."""

    COMMAND_RECEIVED = "COMMAND_RECEIVED"
    COMMAND_CREATED = "COMMAND_CREATED"
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
class ControlEvent:
    """A single immutable control-plane event (§9)."""

    event_id: str
    event_type: str
    command_id: str
    timestamp: datetime
    correlation_id: str
    causation_id: str | None
    sequence: int
    payload: dict[str, Any] = field(default_factory=dict)


class InMemoryEventStore:
    """Append-only in-memory event store.

    Each command gets a monotonically increasing ``sequence`` so the correct
    business order can be rebuilt even if events arrive out of order (§10).
    """

    def __init__(self) -> None:
        self._events: list[ControlEvent] = []
        self._command_sequences: dict[str, int] = {}
        self._event_sequence = 0

    def append(
        self,
        *,
        event_type: str,
        command_id: str,
        correlation_id: str,
        causation_id: str | None = None,
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ControlEvent:
        self._event_sequence += 1
        command_sequence = self._command_sequences.get(command_id, 0) + 1
        self._command_sequences[command_id] = command_sequence
        event = ControlEvent(
            event_id=f"EVT-{self._event_sequence:04d}",
            event_type=event_type,
            command_id=command_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            causation_id=causation_id,
            sequence=command_sequence,
            payload=dict(payload or {}),
        )
        self._events.append(event)
        return event

    def all(self) -> tuple[ControlEvent, ...]:
        return tuple(self._events)

    def events(self, command_id: str) -> tuple[ControlEvent, ...]:
        """All events for one command, ordered by sequence (§10)."""
        return tuple(
            sorted(
                (event for event in self._events if event.command_id == command_id),
                key=lambda event: event.sequence,
            )
        )

    def by_correlation_id(self, correlation_id: str) -> tuple[ControlEvent, ...]:
        return tuple(
            event
            for event in self._events
            if event.correlation_id == correlation_id
        )

    def __len__(self) -> int:
        return len(self._events)

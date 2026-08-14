"""Event sink and transactional outbox (Commit 29 Part 1.5 §12, §47-52).

The Control Plane publishes events through an ``EventSink`` abstraction so it
never depends on a concrete message system (Kafka / Event Store / ...).

State changes and their events must be committed atomically (§48): the
``OutboxStore`` keeps events PENDING inside the same transaction as the
command state, and a background ``OutboxPublisher`` drains it to the sink.
Event delivery failure never downgrades an already-succeeded command (§52).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from .event import ControlEvent


class EventPublishError(Exception):
    """The event sink is temporarily unavailable (§59)."""


class EventSink(Protocol):
    """Destination for published control events (§12)."""

    def publish(self, event: ControlEvent) -> None: ...


class InMemoryEventSink:
    """In-memory sink that can be switched into a failing state for tests (§59)."""

    def __init__(self) -> None:
        self._published: list[ControlEvent] = []
        self._failed = False

    def publish(self, event: ControlEvent) -> None:
        if self._failed:
            raise EventPublishError("event sink unavailable")
        self._published.append(event)

    def fail(self) -> None:
        self._failed = True

    def recover(self) -> None:
        self._failed = False

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def published(self) -> tuple[ControlEvent, ...]:
        return tuple(self._published)


class OutboxState(str, Enum):
    """Event delivery lifecycle (§51)."""

    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass
class OutboxEntry:
    """A durable, not-yet-published event (§48-50)."""

    entry_id: str
    command_id: str
    event_type: str
    correlation_id: str
    payload: dict[str, Any]
    state: OutboxState = OutboxState.PENDING
    retry_count: int = 0
    published_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PublishResult:
    """Result of one outbox flush (§50)."""

    published: int = 0
    failed: int = 0
    pending: int = 0


class OutboxStore:
    """Durable outbox: events appended atomically with command state (§48)."""

    def __init__(self) -> None:
        self._entries: list[OutboxEntry] = []
        self._sequence = 0

    def append(
        self,
        *,
        command_id: str,
        event_type: str,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> OutboxEntry:
        self._sequence += 1
        entry = OutboxEntry(
            entry_id=f"OUT-{self._sequence:04d}",
            command_id=command_id,
            event_type=event_type,
            correlation_id=correlation_id,
            payload=dict(payload or {}),
        )
        self._entries.append(entry)
        return entry

    def pending(self, command_id: str | None = None) -> tuple[OutboxEntry, ...]:
        entries = (
            self._entries
            if command_id is None
            else [entry for entry in self._entries if entry.command_id == command_id]
        )
        return tuple(entry for entry in entries if entry.state is OutboxState.PENDING)

    def has_pending(self, command_id: str) -> bool:
        return bool(self.pending(command_id))

    def mark_publishing(self, entry_id: str) -> OutboxEntry:
        entry = self._get(entry_id)
        entry.state = OutboxState.PUBLISHING
        return entry

    def mark_published(self, entry_id: str, published_at: datetime | None = None) -> OutboxEntry:
        entry = self._get(entry_id)
        entry.state = OutboxState.PUBLISHED
        entry.published_at = published_at or datetime.now(timezone.utc)
        return entry

    def mark_failed(self, entry_id: str) -> OutboxEntry:
        entry = self._get(entry_id)
        entry.state = OutboxState.FAILED
        entry.retry_count += 1
        return entry

    def _get(self, entry_id: str) -> OutboxEntry:
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return entry
        raise KeyError(f"outbox entry not found: {entry_id}")

    def all(self) -> tuple[OutboxEntry, ...]:
        return tuple(self._entries)


class OutboxPublisher:
    """Background publisher: drains PENDING entries to the event sink (§50).

    A failing sink never raises into the caller of a command - it marks the
    entry FAILED for retry and returns the count in ``PublishResult``.
    """

    def __init__(self, outbox: OutboxStore, sink: EventSink) -> None:
        self.outbox = outbox
        self.sink = sink

    def flush(self, command_id: str | None = None) -> PublishResult:
        published = 0
        failed = 0
        pending = self.outbox.pending(command_id)
        for entry in pending:
            self.outbox.mark_publishing(entry.entry_id)
            event = ControlEvent(
                event_id=entry.entry_id,
                event_type=entry.event_type,
                command_id=entry.command_id,
                timestamp=datetime.now(timezone.utc),
                correlation_id=entry.correlation_id,
                causation_id=None,
                sequence=0,
                payload=dict(entry.payload),
            )
            try:
                self.sink.publish(event)
            except EventPublishError:
                self.outbox.mark_failed(entry.entry_id)
                failed += 1
                continue
            self.outbox.mark_published(entry.entry_id)
            published += 1
        return PublishResult(
            published=published,
            failed=failed,
            pending=len(self.outbox.pending(command_id)),
        )

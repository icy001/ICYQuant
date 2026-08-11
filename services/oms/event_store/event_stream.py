"""EventStream — represents the event stream for a single order."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_errors import (
    EventSequenceGapError,
    EventConcurrencyConflictError,
    DuplicateEventError,
    EventCollisionError,
)


@dataclass
class EventStream:
    """An append-only event stream for a single order.

    The stream enforces:
      - Monotonic sequence numbers (no gaps)
      - Hash chain integrity
      - Optimistic concurrency control (expected_sequence)
      - Duplicate detection
      - Terminal event protection (no appends after terminal)
    """

    order_id: str = ""
    events: List[OrderEvent] = field(default_factory=list)
    version: int = 0  # number of events appended
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())
    is_closed: bool = False  # True after a terminal event

    @property
    def next_sequence(self) -> int:
        """The next available sequence number."""
        return self.version + 1

    @property
    def last_sequence(self) -> int:
        """The sequence of the last event (0 if empty)."""
        return self.version

    @property
    def last_event_hash(self) -> str:
        """Hash of the last event (empty string if stream is empty)."""
        if not self.events:
            return ""
        return self.events[-1].event_hash

    @property
    def is_empty(self) -> bool:
        return len(self.events) == 0

    # ── Append ─────────────────────────────────────

    def append(self, event: OrderEvent,
               expected_sequence: Optional[int] = None) -> OrderEvent:
        """Append an event to the stream.

        Args:
            event: The event to append.
            expected_sequence: For optimistic concurrency. If provided,
                must match the current next_sequence.

        Raises:
            EventStreamClosedError: if stream already has a terminal event.
            EventConcurrencyConflictError: if expected_sequence mismatch.
            EventSequenceGapError: if event.sequence has a gap.
            DuplicateEventError: if event_id or sequence already exists
                with identical content (idempotent replay).
            EventCollisionError: if event_id or sequence already exists
                with different content.
        """
        if self.is_closed:
            from .event_store_errors import EventStreamClosedError
            raise EventStreamClosedError(self.order_id)

        # Optimistic concurrency check
        if expected_sequence is not None:
            if expected_sequence != self.next_sequence:
                raise EventConcurrencyConflictError(
                    self.order_id,
                    expected_sequence=expected_sequence,
                    actual_sequence=self.next_sequence,
                )

        # Duplicate detection — check BEFORE sequence validation
        # so that idempotent replays (same event_id + sequence) are
        # caught before the sequence gap error.
        for existing in self.events:
            if existing.event_id == event.event_id:
                if existing.fingerprint() == event.fingerprint():
                    raise DuplicateEventError(
                        self.order_id, event.event_id,
                        event.sequence, idempotent=True,
                    )
                else:
                    raise EventCollisionError(
                        self.order_id, event.event_id, event.sequence,
                    )
            if existing.sequence == event.sequence:
                if existing.fingerprint() == event.fingerprint():
                    raise DuplicateEventError(
                        self.order_id, event.event_id,
                        event.sequence, idempotent=True,
                    )
                else:
                    raise EventCollisionError(
                        self.order_id, event.event_id, event.sequence,
                    )

        # Sequence validation (after duplicate check)
        expected_seq = self.next_sequence
        if event.sequence != expected_seq:
            raise EventSequenceGapError(
                self.order_id, expected=expected_seq, actual=event.sequence,
            )

        # Set hash chain
        event.previous_event_hash = self.last_event_hash
        if not event.is_sealed:
            event.seal()

        self.events.append(event)
        self.version += 1
        self.updated_at = time.time()

        # Check if terminal
        if event.event_type.is_terminal:
            self.is_closed = True

        return event

    # ── Read ───────────────────────────────────────

    def read_all(self) -> List[OrderEvent]:
        """Read all events in sequence order."""
        return list(self.events)

    def read_from(self, sequence: int) -> List[OrderEvent]:
        """Read events from the given sequence (inclusive)."""
        return [e for e in self.events if e.sequence >= sequence]

    def read_until(self, sequence: int) -> List[OrderEvent]:
        """Read events up to and including the given sequence."""
        return [e for e in self.events if e.sequence <= sequence]

    def read_range(self, start: int, end: int) -> List[OrderEvent]:
        """Read events in [start, end] inclusive."""
        return [e for e in self.events if start <= e.sequence <= end]

    def get_event(self, sequence: int) -> Optional[OrderEvent]:
        """Get a specific event by sequence number."""
        for e in self.events:
            if e.sequence == sequence:
                return e
        return None

    def get_latest(self) -> Optional[OrderEvent]:
        """Get the most recent event."""
        return self.events[-1] if self.events else None

    # ── Iteration ──────────────────────────────────

    def __iter__(self) -> Iterator[OrderEvent]:
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)

    # ── Info ───────────────────────────────────────

    def get_lineage_id(self) -> str:
        """Get the lineage_id from the first event (if any)."""
        return self.events[0].lineage_id if self.events else ""

    def get_flow_id(self) -> str:
        return self.events[0].flow_id if self.events else ""

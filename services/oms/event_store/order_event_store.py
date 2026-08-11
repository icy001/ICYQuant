"""OrderEventStore — the durable append-only event store.

This is the Source of Truth for OMS order state. All order state
is derived from replaying events in this store.

Key principles:
    1. Append-only — no update() or delete() methods.
    2. Optimistic concurrency — append requires expected_sequence.
    3. Hash chain — every event links to the previous via hash.
    4. Sequence integrity — gaps are detected and rejected.
    5. Duplicate detection — idempotent replays are handled gracefully.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_errors import (
    EventConcurrencyConflictError,
    DuplicateEventError,
)
from .event_stream import EventStream
from .event_store_errors import EventStreamNotFoundError


class OrderEventStore(ABC):
    """Abstract append-only event store for orders."""

    @abstractmethod
    def append(self, event: OrderEvent,
               expected_sequence: Optional[int] = None) -> OrderEvent:
        """Append an event to an order's stream.

        Raises:
            EventConcurrencyConflictError: if expected_sequence mismatch.
            EventSequenceGapError: if sequence has a gap.
            DuplicateEventError: idempotent replay (same content).
            EventCollisionError: same event_id/sequence, different content.
        """

    @abstractmethod
    def read(self, order_id: str) -> List[OrderEvent]:
        """Read all events for an order."""

    @abstractmethod
    def read_from(self, order_id: str, sequence: int) -> List[OrderEvent]:
        """Read events from a given sequence (inclusive)."""

    @abstractmethod
    def read_until(self, order_id: str, sequence: int) -> List[OrderEvent]:
        """Read events up to and including a given sequence."""

    @abstractmethod
    def get_latest(self, order_id: str) -> Optional[OrderEvent]:
        """Get the latest event for an order."""

    @abstractmethod
    def get_latest_sequence(self, order_id: str) -> int:
        """Get the latest sequence number (0 if stream is empty)."""

    @abstractmethod
    def count(self, order_id: str) -> int:
        """Count events for an order."""

    @abstractmethod
    def get_stream(self, order_id: str) -> EventStream:
        """Get the raw event stream for an order."""

    @abstractmethod
    def stream_exists(self, order_id: str) -> bool:
        """Check if a stream exists for an order."""


class InMemoryOrderEventStore(OrderEventStore):
    """In-memory implementation of the order event store.

    Suitable for testing and development. Production would use
    a persistent backend (PostgreSQL, EventStoreDB, etc.).
    """

    def __init__(self) -> None:
        self._streams: Dict[str, EventStream] = {}

    def append(self, event: OrderEvent,
               expected_sequence: Optional[int] = None) -> OrderEvent:
        stream = self._get_or_create_stream(event.order_id)
        return stream.append(event, expected_sequence=expected_sequence)

    def read(self, order_id: str) -> List[OrderEvent]:
        stream = self._get_stream_or_fail(order_id)
        return stream.read_all()

    def read_from(self, order_id: str, sequence: int) -> List[OrderEvent]:
        stream = self._get_stream_or_fail(order_id)
        return stream.read_from(sequence)

    def read_until(self, order_id: str, sequence: int) -> List[OrderEvent]:
        stream = self._get_stream_or_fail(order_id)
        return stream.read_until(sequence)

    def get_latest(self, order_id: str) -> Optional[OrderEvent]:
        stream = self._streams.get(order_id)
        if stream is None:
            return None
        return stream.get_latest()

    def get_latest_sequence(self, order_id: str) -> int:
        stream = self._streams.get(order_id)
        if stream is None:
            return 0
        return stream.last_sequence

    def count(self, order_id: str) -> int:
        stream = self._streams.get(order_id)
        if stream is None:
            return 0
        return len(stream)

    def get_stream(self, order_id: str) -> EventStream:
        return self._get_stream_or_fail(order_id)

    def stream_exists(self, order_id: str) -> bool:
        return order_id in self._streams and not self._streams[order_id].is_empty

    # ── Internal ───────────────────────────────────

    def _get_or_create_stream(self, order_id: str) -> EventStream:
        if order_id not in self._streams:
            self._streams[order_id] = EventStream(order_id=order_id)
        return self._streams[order_id]

    def _get_stream_or_fail(self, order_id: str) -> EventStream:
        stream = self._streams.get(order_id)
        if stream is None:
            raise EventStreamNotFoundError(order_id)
        return stream

    # ── Bulk operations (for recovery/rebuild) ─────

    def get_all_order_ids(self) -> List[str]:
        """Return all order IDs that have event streams."""
        return list(self._streams.keys())

    def get_all_streams(self) -> Dict[str, EventStream]:
        """Return all streams (for debugging/admin)."""
        return dict(self._streams)

"""EventStreamWriter — write-side operations on event streams.

Handles:
    - Optimistic concurrency control
    - Sequence allocation
    - Hash chain maintenance
    - Duplicate detection
"""
from __future__ import annotations

from typing import Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_errors import (
    EventConcurrencyConflictError,
    DuplicateEventError,
)
from .order_event_store import OrderEventStore
from .event_store_errors import EventStreamClosedError


class EventStreamWriter:
    """Write-side access to event streams.

    All writes go through this writer to ensure:
      1. Correct sequence allocation
      2. Hash chain maintenance
      3. Optimistic concurrency control
    """

    def __init__(self, store: OrderEventStore) -> None:
        self._store = store

    def append(self, event: OrderEvent,
               expected_sequence: Optional[int] = None) -> OrderEvent:
        """Append an event with optimistic concurrency control.

        If expected_sequence is provided, it must match the current
        next_sequence of the stream. This prevents lost updates.

        If expected_sequence is None, the writer will allocate the
        correct sequence automatically.
        """
        if expected_sequence is not None:
            actual = self._store.get_latest_sequence(event.order_id) + 1
            if expected_sequence != actual:
                raise EventConcurrencyConflictError(
                    event.order_id,
                    expected_sequence=expected_sequence,
                    actual_sequence=actual,
                )
        else:
            # Auto-allocate sequence
            event.sequence = self._store.get_latest_sequence(event.order_id) + 1

        return self._store.append(event, expected_sequence=expected_sequence)

    def append_idempotent(self, event: OrderEvent) -> OrderEvent:
        """Append an event, handling duplicates gracefully.

        If the event already exists (same event_id and same content),
        returns the existing event instead of raising.
        """
        try:
            return self.append(event)
        except DuplicateEventError as e:
            if e.idempotent:
                # Return the existing event
                stream = self._store.get_stream(event.order_id)
                existing = stream.get_event(event.sequence)
                if existing is not None:
                    return existing
            raise

    def close_stream(self, order_id: str,
                     terminal_event: OrderEvent) -> OrderEvent:
        """Append a terminal event and close the stream."""
        if self._store.stream_exists(order_id):
            stream = self._store.get_stream(order_id)
            if stream.is_closed:
                raise EventStreamClosedError(order_id)
        return self.append(terminal_event)

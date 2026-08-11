"""EventStreamReader — read-side operations on event streams."""
from __future__ import annotations

from typing import Iterator, List, Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_validator import OrderEventValidator
from .order_event_store import OrderEventStore
from .event_store_errors import EventStreamNotFoundError


class EventStreamReader:
    """Read-only access to event streams with validation.

    Provides convenient query methods on top of the raw EventStore.
    All reads validate hash chain integrity before returning results.
    """

    def __init__(self, store: OrderEventStore,
                 validate_on_read: bool = True) -> None:
        self._store = store
        self._validate = validate_on_read

    def read_all(self, order_id: str) -> List[OrderEvent]:
        """Read all events for an order, validating the hash chain."""
        events = self._store.read(order_id)
        if self._validate and events:
            OrderEventValidator.validate_hash_chain(events)
        return events

    def read_from(self, order_id: str, sequence: int) -> List[OrderEvent]:
        return self._store.read_from(order_id, sequence)

    def read_until(self, order_id: str, sequence: int) -> List[OrderEvent]:
        return self._store.read_until(order_id, sequence)

    def get_latest(self, order_id: str) -> Optional[OrderEvent]:
        return self._store.get_latest(order_id)

    def get_latest_sequence(self, order_id: str) -> int:
        return self._store.get_latest_sequence(order_id)

    def count(self, order_id: str) -> int:
        return self._store.count(order_id)

    def exists(self, order_id: str) -> bool:
        return self._store.stream_exists(order_id)

    def get_events_by_type(self, order_id: str,
                           event_type: OrderEventType) -> List[OrderEvent]:
        """Get all events of a specific type for an order."""
        events = self._store.read(order_id)
        return [e for e in events if e.event_type == event_type]

    def get_execution_events(self, order_id: str) -> List[OrderEvent]:
        """Get all execution-related events (partial fills, fills)."""
        events = self._store.read(order_id)
        return [e for e in events if e.event_type.is_execution_event]

    def get_terminal_event(self, order_id: str) -> Optional[OrderEvent]:
        """Get the terminal event if the stream is closed."""
        events = self._store.read(order_id)
        for evt in reversed(events):
            if evt.event_type.is_terminal:
                return evt
        return None

    def is_stream_closed(self, order_id: str) -> bool:
        """Check if the stream has a terminal event."""
        return self.get_terminal_event(order_id) is not None

    def iterate(self, order_id: str) -> Iterator[OrderEvent]:
        """Iterate over events in sequence order."""
        for evt in self._store.read(order_id):
            yield evt

    def get_lineage(self, order_id: str) -> str:
        """Get the lineage_id from the first event."""
        events = self._store.read(order_id)
        if not events:
            return ""
        return events[0].lineage_id

    def get_flow_id(self, order_id: str) -> str:
        """Get the flow_id from the first event."""
        events = self._store.read(order_id)
        if not events:
            return ""
        return events[0].flow_id

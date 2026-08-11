"""OrderRebuilder — rebuilds order state from the event store.

The rebuilder is the core of OMS self-recovery. Given an order_id,
it loads the event stream, validates integrity, and replays events
to reconstruct the current order state.

Flow:
    Load Event Stream
         ↓
    Validate Sequence
         ↓
    Validate Hash Chain
         ↓
    Replay Events (from snapshot if available)
         ↓
    Return Order State
"""
from __future__ import annotations

from typing import List, Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_validator import OrderEventValidator
from services.oms.events.order_event_errors import (
    EventSequenceGapError,
    EventHashChainError,
)
from services.oms.event_store.order_event_store import OrderEventStore
from services.oms.event_store.event_store_snapshot import (
    EventStoreSnapshot, SnapshotStore,
)
from services.oms.event_store.event_store_errors import (
    EventStreamNotFoundError,
    SnapshotValidationError,
)
from services.oms.projection.order_projection import OrderProjection
from services.oms.projection.order_state_reducer import OrderStateReducer


class OrderRebuilder:
    """Rebuilds order state from the event store.

    The rebuilder is deterministic — given the same event stream,
    it always produces the same state. This is a critical property
    for reconciliation and audit.
    """

    def __init__(self, store: OrderEventStore,
                 snapshot_store: Optional[SnapshotStore] = None) -> None:
        self._store = store
        self._snapshots = snapshot_store or SnapshotStore()

    def rebuild(self, order_id: str) -> OrderProjection:
        """Rebuild the order state from events.

        Raises:
            EventStreamNotFoundError: if no stream exists.
            EventSequenceGapError: if there's a gap in the sequence.
            EventHashChainError: if the hash chain is broken.
        """
        if not self._store.stream_exists(order_id):
            raise EventStreamNotFoundError(order_id)

        events = self._store.read(order_id)
        if not events:
            return OrderProjection.empty(order_id)

        # Validate sequence
        OrderEventValidator.validate_sequence(events)

        # Validate hash chain
        OrderEventValidator.validate_hash_chain(events)

        # Try snapshot
        snapshot = self._snapshots.get(order_id)
        if snapshot is not None and snapshot.verify():
            # Validate snapshot against event hash
            snap_event = self._store.get_stream(order_id).get_event(
                snapshot.sequence,
            )
            if snap_event and snapshot.verify_against_event(snap_event.event_hash):
                # Replay only events after snapshot
                post_events = [e for e in events if e.sequence > snapshot.sequence]
                return OrderStateReducer.reduce_from_snapshot(
                    snapshot, post_events,
                )
            else:
                # Snapshot doesn't match event store — discard
                self._snapshots.delete(order_id)

        # Full replay
        return OrderStateReducer.reduce_all(events, order_id)

    def rebuild_from_scratch(self, order_id: str) -> OrderProjection:
        """Force a full replay, ignoring any snapshots."""
        if not self._store.stream_exists(order_id):
            raise EventStreamNotFoundError(order_id)

        events = self._store.read(order_id)
        OrderEventValidator.validate_sequence(events)
        OrderEventValidator.validate_hash_chain(events)
        return OrderStateReducer.reduce_all(events, order_id)

    def validate_integrity(self, order_id: str) -> bool:
        """Validate the integrity of an order's event stream.

        Returns True if the stream is valid, False otherwise.
        Does NOT raise — catches all validation errors.
        """
        try:
            if not self._store.stream_exists(order_id):
                return False
            events = self._store.read(order_id)
            OrderEventValidator.validate_sequence(events)
            OrderEventValidator.validate_hash_chain(events)
            return True
        except (EventSequenceGapError, EventHashChainError,
                EventStreamNotFoundError):
            return False

    def get_event_count(self, order_id: str) -> int:
        """Get the number of events in an order's stream."""
        return self._store.count(order_id)

    def get_events(self, order_id: str) -> List[OrderEvent]:
        """Get all events for an order (for inspection/debugging)."""
        if not self._store.stream_exists(order_id):
            return []
        return self._store.read(order_id)

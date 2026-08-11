"""OrderProjector — builds and maintains order projections from events.

The projector subscribes to the event store and maintains up-to-date
projections. It also supports rebuilding projections from scratch.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_validator import OrderEventValidator
from services.oms.event_store.order_event_store import OrderEventStore
from services.oms.event_store.event_store_snapshot import (
    EventStoreSnapshot, SnapshotStore,
)
from .order_projection import OrderProjection
from .order_state_reducer import OrderStateReducer


class OrderProjector:
    """Builds and maintains order projections from the event store.

    Supports:
      - Live projection updates (apply new events)
      - Full rebuild from event store
      - Rebuild from snapshot + events after snapshot
      - Projection lag tracking
    """

    def __init__(self, store: OrderEventStore,
                 snapshot_store: Optional[SnapshotStore] = None,
                 use_snapshots: bool = True) -> None:
        self._store = store
        self._snapshots = snapshot_store or SnapshotStore()
        self._use_snapshots = use_snapshots
        self._projections: Dict[str, OrderProjection] = {}

    # ── Live updates ───────────────────────────────

    def apply_event(self, event: OrderEvent) -> OrderProjection:
        """Apply a single event to the projection for its order."""
        current = self._projections.get(event.order_id)
        if current is None:
            current = OrderProjection.empty(event.order_id)
        new_state = OrderStateReducer.reduce(current, event)
        self._projections[event.order_id] = new_state
        return new_state

    def apply_events(self, events: List[OrderEvent]) -> OrderProjection:
        """Apply multiple events in sequence."""
        if not events:
            raise ValueError("Cannot apply empty event list")
        order_id = events[0].order_id
        state = self._projections.get(order_id,
                                       OrderProjection.empty(order_id))
        for event in events:
            state = OrderStateReducer.reduce(state, event)
        self._projections[order_id] = state
        return state

    # ── Full rebuild ───────────────────────────────

    def rebuild(self, order_id: str) -> OrderProjection:
        """Rebuild a projection from the event store.

        If a valid snapshot exists, starts from the snapshot and
        replays only events after the snapshot sequence.
        """
        if not self._store.stream_exists(order_id):
            self._projections.pop(order_id, None)
            return OrderProjection.empty(order_id)

        # Try snapshot
        if self._use_snapshots:
            snapshot = self._snapshots.get(order_id)
            if snapshot is not None and snapshot.verify():
                events = self._store.read_from(order_id, snapshot.sequence + 1)
                state = OrderStateReducer.reduce_from_snapshot(snapshot, events)
                self._projections[order_id] = state
                return state

        # Full replay
        events = self._store.read(order_id)
        if events:
            OrderEventValidator.validate_hash_chain(events)
        state = OrderStateReducer.reduce_all(events, order_id)
        self._projections[order_id] = state
        return state

    def rebuild_all(self) -> Dict[str, OrderProjection]:
        """Rebuild all projections from the event store."""
        for order_id in self._store.get_all_order_ids():
            self.rebuild(order_id)
        return dict(self._projections)

    # ── Query ──────────────────────────────────────

    def get(self, order_id: str) -> Optional[OrderProjection]:
        """Get the cached projection (may be stale)."""
        return self._projections.get(order_id)

    def get_or_rebuild(self, order_id: str) -> OrderProjection:
        """Get projection, rebuilding if not cached."""
        proj = self._projections.get(order_id)
        if proj is None:
            proj = self.rebuild(order_id)
        return proj

    def get_lag(self, order_id: str) -> int:
        """Calculate projection lag (events behind the store)."""
        proj = self._projections.get(order_id)
        if proj is None:
            return self._store.count(order_id)
        latest = self._store.get_latest_sequence(order_id)
        return latest - proj.last_event_sequence

    def is_stale(self, order_id: str) -> bool:
        """Check if the projection is behind the event store."""
        return self.get_lag(order_id) > 0

    # ── Snapshot management ────────────────────────

    def create_snapshot(self, order_id: str) -> Optional[EventStoreSnapshot]:
        """Create a snapshot at the current projection state."""
        proj = self._projections.get(order_id)
        if proj is None:
            return None
        snapshot = EventStoreSnapshot.create(
            order_id=order_id,
            sequence=proj.last_event_sequence,
            status=proj.status,
            filled_quantity=proj.filled_quantity,
            remaining_quantity=proj.remaining_quantity,
            cancelled_quantity=proj.cancelled_quantity,
            original_quantity=proj.original_quantity,
            average_price=proj.average_price,
            last_event_hash=proj.last_event_hash,
        )
        self._snapshots.save(snapshot)
        return snapshot

    def invalidate(self, order_id: str) -> None:
        """Mark a projection as stale (requires rebuild)."""
        proj = self._projections.get(order_id)
        if proj is not None:
            proj.mark_stale()

    def remove(self, order_id: str) -> None:
        """Remove a projection from the cache."""
        self._projections.pop(order_id, None)

    # ── Bulk operations ────────────────────────────

    def get_all_projections(self) -> Dict[str, OrderProjection]:
        return dict(self._projections)

    def get_terminal_projections(self) -> List[OrderProjection]:
        return [p for p in self._projections.values() if p.is_terminal]

    def get_active_projections(self) -> List[OrderProjection]:
        return [p for p in self._projections.values() if not p.is_terminal]

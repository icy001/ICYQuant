"""Lifecycle Event Store — Event-sourced persistence layer.

Records all order lifecycle events for replay, audit, and recovery.
Implements Event Sourcing pattern where events are the source of truth.

Pipeline:
    Order Event → Persist → Replay → Audit

Features:
- Immutable event log
- Event replay for state reconstruction
- Event query by order, type, and time range
- Async-compatible storage interface
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class StoredEvent:
    """An immutable event stored in the event store."""
    event_id: str
    order_id: str
    event_type: str
    from_status: str
    to_status: str
    sequence_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "event_type": self.event_type,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "sequence_id": self.sequence_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=data["event_id"],
            order_id=data["order_id"],
            event_type=data["event_type"],
            from_status=data["from_status"],
            to_status=data["to_status"],
            sequence_id=data.get("sequence_id", 0),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data["timestamp"], str)
                else data["timestamp"]
            ),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


class LifecycleEventStore:
    """Event-sourced storage for order lifecycle events.

    Stores all events immutably. Supports event replay to reconstruct
    order state from history, and querying events for audit purposes.

    In production, this would be backed by a database. The default
    implementation uses in-memory storage suitable for development
    and testing.

    Usage::

        store = LifecycleEventStore()
        await store.store_event(order_id="...", event_type="fill", ...)
        events = await store.get_events(order_id="...")
        state = await store.replay(order_id="...")
    """

    def __init__(self) -> None:
        # order_id → list of events (sorted by sequence_id)
        self._events: dict[str, list[StoredEvent]] = defaultdict(list)
        # event_id → StoredEvent for direct lookup
        self._by_id: dict[str, StoredEvent] = {}
        # order_id → current sequence
        self._sequences: dict[str, int] = defaultdict(int)

    async def store_event(
        self,
        order_id: str,
        event_type: str,
        from_status: str,
        to_status: str,
        payload: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> StoredEvent:
        """Store a lifecycle event.

        Args:
            order_id: Order identifier
            event_type: Type of event (e.g., 'fill', 'cancel')
            from_status: Status before the event
            to_status: Status after the event
            payload: Event-specific data
            metadata: Additional context
            event_id: Optional custom event ID

        Returns:
            The stored event
        """
        if event_id is None:
            event_id = str(uuid.uuid4())

        self._sequences[order_id] += 1
        sequence_id = self._sequences[order_id]

        event = StoredEvent(
            event_id=event_id,
            order_id=order_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            sequence_id=sequence_id,
            payload=payload or {},
            metadata=metadata or {},
        )

        self._events[order_id].append(event)
        self._by_id[event_id] = event

        logger.debug(
            f"Event stored: order={order_id}, type={event_type}, "
            f"seq={sequence_id}, {from_status} -> {to_status}"
        )

        return event

    async def get_events(
        self,
        order_id: str,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[StoredEvent]:
        """Query events for an order with optional filters.

        Args:
            order_id: Order identifier
            event_type: Filter by event type
            since: Filter events after this timestamp
            until: Filter events before this timestamp

        Returns:
            Matching events in sequence order
        """
        events = self._events.get(order_id, [])

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if since:
            events = [e for e in events if e.timestamp >= since]
        if until:
            events = [e for e in events if e.timestamp <= until]

        return sorted(events, key=lambda e: e.sequence_id)

    async def get_event(self, event_id: str) -> Optional[StoredEvent]:
        """Get a single event by ID.

        Args:
            event_id: Event identifier

        Returns:
            The event or None if not found
        """
        return self._by_id.get(event_id)

    async def get_last_event(self, order_id: str) -> Optional[StoredEvent]:
        """Get the most recent event for an order.

        Args:
            order_id: Order identifier

        Returns:
            The last event or None
        """
        events = self._events.get(order_id, [])
        if not events:
            return None
        return sorted(events, key=lambda e: e.sequence_id)[-1]

    async def get_event_count(self, order_id: str) -> int:
        """Get the number of events for an order.

        Args:
            order_id: Order identifier

        Returns:
            Event count
        """
        return len(self._events.get(order_id, []))

    async def get_sequence(self, order_id: str) -> int:
        """Get the current sequence number for an order.

        Args:
            order_id: Order identifier

        Returns:
            Current sequence number
        """
        return self._sequences.get(order_id, 0)

    async def replay(self, order_id: str) -> list[StoredEvent]:
        """Replay all events for an order (for state reconstruction).

        Args:
            order_id: Order identifier

        Returns:
            All events in sequence order
        """
        events = self._events.get(order_id, [])
        return sorted(events, key=lambda e: e.sequence_id)

    async def iterate_events(
        self, order_id: str, batch_size: int = 100
    ) -> AsyncIterator[list[StoredEvent]]:
        """Iterate events in batches for large order histories.

        Args:
            order_id: Order identifier
            batch_size: Events per batch

        Yields:
            Batches of events in sequence order
        """
        events = sorted(self._events.get(order_id, []), key=lambda e: e.sequence_id)
        for i in range(0, len(events), batch_size):
            yield events[i : i + batch_size]

    async def delete_events(self, order_id: str) -> int:
        """Delete all events for an order.

        Args:
            order_id: Order identifier

        Returns:
            Number of events deleted
        """
        events = self._events.pop(order_id, [])
        for e in events:
            self._by_id.pop(e.event_id, None)
        self._sequences.pop(order_id, None)
        logger.info(f"Deleted {len(events)} events for order {order_id}")
        return len(events)

    def to_dict(self) -> dict[str, Any]:
        """Serialize store state."""
        return {
            "total_orders": len(self._events),
            "total_events": sum(len(evts) for evts in self._events.values()),
            "orders": {
                oid: {
                    "event_count": len(evts),
                    "sequence": self._sequences.get(oid, 0),
                    "last_event_type": (
                        evts[-1].event_type if evts else None
                    ),
                    "last_status": (
                        evts[-1].to_status if evts else None
                    ),
                }
                for oid, evts in self._events.items()
            },
        }

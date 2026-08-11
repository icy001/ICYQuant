"""OrderEventStore port — append-only event storage for lifecycle events."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from services.oms.domain.order_lifecycle import OrderLifecycleEvent, LifecycleEventType


class OrderEventStore(ABC):
    """Append-only store for order lifecycle events."""

    @abstractmethod
    def append(self, event: OrderLifecycleEvent) -> None:
        """Append an event. Events are immutable once stored."""

    @abstractmethod
    def get_by_order(self, order_id: str) -> List[OrderLifecycleEvent]:
        """Get all events for an order, in sequence."""

    @abstractmethod
    def get_by_lineage(self, lineage_id: str) -> List[OrderLifecycleEvent]:
        """Get all events for a lineage."""

    @abstractmethod
    def get_by_type(self,
                    event_type: LifecycleEventType) -> List[OrderLifecycleEvent]:
        """Get all events of a specific type."""

    @abstractmethod
    def get_last_event(self, order_id: str) -> Optional[OrderLifecycleEvent]:
        """Get the most recent event for an order."""


class InMemoryOrderEventStore(OrderEventStore):
    """In-memory event store for testing."""

    def __init__(self) -> None:
        self._events: List[OrderLifecycleEvent] = []

    def append(self, event: OrderLifecycleEvent) -> None:
        self._events.append(event)

    def get_by_order(self, order_id: str) -> List[OrderLifecycleEvent]:
        return [e for e in self._events if e.order_id == order_id]

    def get_by_lineage(self, lineage_id: str) -> List[OrderLifecycleEvent]:
        return [e for e in self._events if e.lineage_id == lineage_id]

    def get_by_type(self,
                    event_type: LifecycleEventType) -> List[OrderLifecycleEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def get_last_event(self, order_id: str) -> Optional[OrderLifecycleEvent]:
        events = self.get_by_order(order_id)
        return events[-1] if events else None

    @property
    def count(self) -> int:
        return len(self._events)

"""OrderLifecycle — domain events that drive the order lifecycle."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .order_status import OrderStatus


# ── Lifecycle Event Types ──────────────────────────


class LifecycleEventType(Enum):
    """Events that drive order state transitions."""

    ORDER_RECEIVED = auto()
    ORDER_ACCEPTED = auto()
    ORDER_CREATED = auto()
    ORDER_ROUTING_STARTED = auto()
    ORDER_WORKING = auto()
    ORDER_PARTIAL_FILL = auto()
    ORDER_FILLED = auto()

    ORDER_CANCEL_REQUESTED = auto()
    ORDER_CANCEL_CONFIRMED = auto()
    ORDER_CANCELLED = auto()

    ORDER_REJECTED = auto()
    ORDER_EXPIRED = auto()
    ORDER_FAILED = auto()

    AMEND_REQUESTED = auto()
    AMEND_CONFIRMED = auto()

    @property
    def label(self) -> str:
        _labels = {
            LifecycleEventType.ORDER_RECEIVED: "Order Received",
            LifecycleEventType.ORDER_ACCEPTED: "Order Accepted",
            LifecycleEventType.ORDER_CREATED: "Order Created",
            LifecycleEventType.ORDER_ROUTING_STARTED: "Routing Started",
            LifecycleEventType.ORDER_WORKING: "Order Working",
            LifecycleEventType.ORDER_PARTIAL_FILL: "Partial Fill",
            LifecycleEventType.ORDER_FILLED: "Order Filled",
            LifecycleEventType.ORDER_CANCEL_REQUESTED: "Cancel Requested",
            LifecycleEventType.ORDER_CANCEL_CONFIRMED: "Cancel Confirmed",
            LifecycleEventType.ORDER_CANCELLED: "Order Cancelled",
            LifecycleEventType.ORDER_REJECTED: "Order Rejected",
            LifecycleEventType.ORDER_EXPIRED: "Order Expired",
            LifecycleEventType.ORDER_FAILED: "Order Failed",
            LifecycleEventType.AMEND_REQUESTED: "Amend Requested",
            LifecycleEventType.AMEND_CONFIRMED: "Amend Confirmed",
        }
        return _labels[self]


# ── Transition Table ──────────────────────────────

# Maps event type → (expected_from_status, target_status)
_EVENT_TRANSITIONS: dict[LifecycleEventType, tuple[tuple[OrderStatus, ...], OrderStatus]] = {
    LifecycleEventType.ORDER_RECEIVED:   ((), OrderStatus.RECEIVED),
    LifecycleEventType.ORDER_ACCEPTED:   ((OrderStatus.RECEIVED,), OrderStatus.ACCEPTED),
    LifecycleEventType.ORDER_CREATED:    ((OrderStatus.ACCEPTED,), OrderStatus.CREATED),
    LifecycleEventType.ORDER_ROUTING_STARTED: ((OrderStatus.CREATED,), OrderStatus.ROUTING),
    LifecycleEventType.ORDER_WORKING:    ((OrderStatus.ROUTING,), OrderStatus.WORKING),
    LifecycleEventType.ORDER_PARTIAL_FILL: ((OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED), OrderStatus.PARTIALLY_FILLED),
    LifecycleEventType.ORDER_FILLED:     ((OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED), OrderStatus.FILLED),
    LifecycleEventType.ORDER_CANCEL_REQUESTED: (
        (OrderStatus.CREATED, OrderStatus.ROUTING, OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.WORKING,
    ),
    LifecycleEventType.ORDER_CANCEL_CONFIRMED: (
        (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.CANCELLED,
    ),
    LifecycleEventType.ORDER_CANCELLED: (
        (OrderStatus.CREATED, OrderStatus.ROUTING, OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.CANCELLED,
    ),
    LifecycleEventType.ORDER_REJECTED: (
        (OrderStatus.RECEIVED, OrderStatus.CREATED, OrderStatus.ROUTING, OrderStatus.WORKING),
        OrderStatus.REJECTED,
    ),
    LifecycleEventType.ORDER_EXPIRED: (
        (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.EXPIRED,
    ),
    LifecycleEventType.ORDER_FAILED: (
        (OrderStatus.ROUTING, OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.FAILED,
    ),
    LifecycleEventType.AMEND_REQUESTED: (
        (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.WORKING,
    ),
    LifecycleEventType.AMEND_CONFIRMED: (
        (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
        OrderStatus.WORKING,
    ),
}


# ── Lifecycle Events ──────────────────────────────


@dataclass
class OrderLifecycleEvent:
    """A single event in the order's lifecycle.

    Every state change is driven by an event, preserving the full
    history of why and how the order reached its current state.
    """

    event_id: str = field(
        default_factory=lambda: f"OL-EVT-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    event_type: LifecycleEventType = LifecycleEventType.ORDER_RECEIVED
    order_id: str = ""
    previous_status: Optional[OrderStatus] = None
    new_status: OrderStatus = OrderStatus.RECEIVED
    lineage_id: str = ""
    certificate_id: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    actor: str = ""
    actor_type: str = ""
    reason: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, event_type: LifecycleEventType,
               order_id: str,
               previous_status: Optional[OrderStatus],
               lineage_id: str = "",
               certificate_id: str = "",
               actor: str = "",
               actor_type: str = "",
               reason: str = "",
               **payload: Any) -> OrderLifecycleEvent:
        """Create and resolve the target status."""
        _, target_status = _EVENT_TRANSITIONS[event_type]
        return cls(
            event_type=event_type,
            order_id=order_id,
            previous_status=previous_status,
            new_status=target_status,
            lineage_id=lineage_id,
            certificate_id=certificate_id,
            actor=actor,
            actor_type=actor_type,
            reason=reason,
            payload=dict(payload),
        )

    @property
    def is_terminal_event(self) -> bool:
        return self.new_status.is_terminal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "order_id": self.order_id,
            "previous_status": self.previous_status.name if self.previous_status else None,
            "new_status": self.new_status.name,
            "lineage_id": self.lineage_id,
            "certificate_id": self.certificate_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "reason": self.reason,
            "payload": dict(self.payload),
        }


@dataclass
class OrderLifecycle:
    """Order lifecycle — ordered list of lifecycle events.

    The lifecycle is append-only: events cannot be removed or reordered.
    """

    order_id: str = ""
    events: List[OrderLifecycleEvent] = field(default_factory=list)
    current_status: OrderStatus = OrderStatus.RECEIVED
    version: int = 0

    def append(self, event: OrderLifecycleEvent) -> None:
        """Append an event, validating the transition."""
        # Validate that event matches current state
        valid_prev, _ = _EVENT_TRANSITIONS[event.event_type]
        if valid_prev and self.current_status not in valid_prev:
            raise LifecycleTransitionError(
                f"Invalid transition: cannot apply {event.event_type.name} "
                f"from status {self.current_status.name}",
                event_type=event.event_type,
                current_status=self.current_status,
            )
        # Terminal protection
        if self.current_status.is_terminal:
            raise LifecycleTransitionError(
                f"Cannot transition from terminal state {self.current_status.name}",
                event_type=event.event_type,
                current_status=self.current_status,
            )

        event.previous_status = self.current_status
        event.new_status = _EVENT_TRANSITIONS[event.event_type][1]
        event.order_id = self.order_id

        self.events.append(event)
        self.current_status = event.new_status
        self.version += 1

    @property
    def event_count(self) -> int:
        return len(self.events)

    def last_event(self) -> Optional[OrderLifecycleEvent]:
        return self.events[-1] if self.events else None

    def get_events_by_type(self,
                           event_type: LifecycleEventType) -> List[OrderLifecycleEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def is_consistent(self) -> bool:
        """Check that the event chain is internally consistent."""
        for i, event in enumerate(self.events):
            if i == 0:
                continue
            prev = self.events[i - 1]
            if event.previous_status != prev.new_status:
                return False
        if self.events and self.current_status != self.events[-1].new_status:
            return False
        return True


# ── Errors ────────────────────────────────────────


class LifecycleTransitionError(Exception):
    def __init__(self, message: str,
                 event_type: LifecycleEventType = LifecycleEventType.ORDER_RECEIVED,
                 current_status: OrderStatus = OrderStatus.RECEIVED) -> None:
        super().__init__(message)
        self.event_type = event_type
        self.current_status = current_status

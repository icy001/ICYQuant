"""OrderEventType — unified event type enum for order lifecycle."""
from __future__ import annotations

from enum import Enum, auto


class OrderEventType(Enum):
    """All events that can appear in an order's event stream."""

    # ── Lifecycle progression ─────────────────────
    ORDER_ACCEPTED = auto()
    ORDER_CREATED = auto()
    ORDER_ROUTING_STARTED = auto()
    ORDER_WORKING = auto()

    # ── Execution ─────────────────────────────────
    ORDER_PARTIAL_FILL = auto()
    ORDER_FILLED = auto()

    # ── Cancel ────────────────────────────────────
    ORDER_CANCEL_REQUESTED = auto()
    ORDER_CANCELLED = auto()

    # ── Terminal ──────────────────────────────────
    ORDER_REJECTED = auto()
    ORDER_EXPIRED = auto()
    ORDER_FAILED = auto()

    # ── Amendments ────────────────────────────────
    ORDER_AMENDED = auto()
    ORDER_SUSPENDED = auto()
    ORDER_RESUMED = auto()

    @property
    def label(self) -> str:
        _labels = {
            OrderEventType.ORDER_ACCEPTED: "Order Accepted",
            OrderEventType.ORDER_CREATED: "Order Created",
            OrderEventType.ORDER_ROUTING_STARTED: "Routing Started",
            OrderEventType.ORDER_WORKING: "Order Working",
            OrderEventType.ORDER_PARTIAL_FILL: "Partial Fill",
            OrderEventType.ORDER_FILLED: "Order Filled",
            OrderEventType.ORDER_CANCEL_REQUESTED: "Cancel Requested",
            OrderEventType.ORDER_CANCELLED: "Order Cancelled",
            OrderEventType.ORDER_REJECTED: "Order Rejected",
            OrderEventType.ORDER_EXPIRED: "Order Expired",
            OrderEventType.ORDER_FAILED: "Order Failed",
            OrderEventType.ORDER_AMENDED: "Order Amended",
            OrderEventType.ORDER_SUSPENDED: "Order Suspended",
            OrderEventType.ORDER_RESUMED: "Order Resumed",
        }
        return _labels[self]

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_EVENTS

    @property
    def is_execution_event(self) -> bool:
        return self in (
            OrderEventType.ORDER_PARTIAL_FILL,
            OrderEventType.ORDER_FILLED,
        )

    @property
    def is_amendment(self) -> bool:
        return self in (
            OrderEventType.ORDER_AMENDED,
            OrderEventType.ORDER_SUSPENDED,
            OrderEventType.ORDER_RESUMED,
        )


_TERMINAL_EVENTS = frozenset({
    OrderEventType.ORDER_FILLED,
    OrderEventType.ORDER_CANCELLED,
    OrderEventType.ORDER_REJECTED,
    OrderEventType.ORDER_EXPIRED,
    OrderEventType.ORDER_FAILED,
})

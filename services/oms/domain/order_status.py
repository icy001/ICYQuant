"""OrderStatus enum — institutional order lifecycle states."""
from __future__ import annotations

from enum import Enum, auto


class OrderStatus(Enum):
    """Strict lifecycle states for institutional orders."""

    # --- Lifecycle states ---
    RECEIVED = auto()
    ACCEPTED = auto()
    CREATED = auto()
    ROUTING = auto()
    WORKING = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()

    # --- Terminal states ---
    CANCELLED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    FAILED = auto()

    # --- Special states ---
    UNKNOWN = auto()

    # ── labels ────────────────────────────────────────

    @property
    def label(self) -> str:
        _labels = {
            OrderStatus.RECEIVED: "Received",
            OrderStatus.ACCEPTED: "Accepted",
            OrderStatus.CREATED: "Created",
            OrderStatus.ROUTING: "Routing",
            OrderStatus.WORKING: "Working",
            OrderStatus.PARTIALLY_FILLED: "Partially Filled",
            OrderStatus.FILLED: "Filled",
            OrderStatus.CANCELLED: "Cancelled",
            OrderStatus.REJECTED: "Rejected",
            OrderStatus.EXPIRED: "Expired",
            OrderStatus.FAILED: "Failed",
            OrderStatus.UNKNOWN: "Unknown",
        }
        return _labels[self]

    # ── classification ────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        return self in _ACTIVE_STATES

    @property
    def is_before_admission(self) -> bool:
        """True before the order has been accepted into OMS."""
        return self in (OrderStatus.RECEIVED,)

    @property
    def can_be_modified(self) -> bool:
        return self in (OrderStatus.CREATED, OrderStatus.WORKING,
                        OrderStatus.PARTIALLY_FILLED)

    @property
    def can_be_cancelled(self) -> bool:
        return self in (OrderStatus.CREATED, OrderStatus.ROUTING,
                        OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED)


_TERMINAL_STATES = frozenset({
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
    OrderStatus.FAILED,
})

_ACTIVE_STATES = frozenset({
    OrderStatus.RECEIVED,
    OrderStatus.ACCEPTED,
    OrderStatus.CREATED,
    OrderStatus.ROUTING,
    OrderStatus.WORKING,
    OrderStatus.PARTIALLY_FILLED,
})

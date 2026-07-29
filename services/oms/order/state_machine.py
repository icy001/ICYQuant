"""Order State Machine.

Enforces strict order lifecycle consistency. Only valid
state transitions are permitted; any illegal transition
raises an error immediately.

Valid transitions:
    CREATED           -> VALIDATED
    VALIDATED         -> ROUTED, REJECTED
    ROUTED            -> SUBMITTED, REJECTED
    SUBMITTED         -> ACKNOWLEDGED, CANCELLED, REJECTED
    ACKNOWLEDGED      -> PARTIALLY_FILLED, FILLED, CANCELLED
    PARTIALLY_FILLED  -> PARTIALLY_FILLED, FILLED, CANCELLED
    FILLED            -> (terminal)
    CANCELLED         -> (terminal)
    REJECTED          -> (terminal)

Illegal example:
    FILLED -> SUBMITTED  (REJECTED)
    CANCELLED -> FILLED  (REJECTED)
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Set

from .models import Order, OrderStatus


class InvalidTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, from_status: OrderStatus, to_status: OrderStatus, order_id: str = "") -> None:
        self.from_status = from_status
        self.to_status = to_status
        self.order_id = order_id
        msg = (
            f"Invalid state transition: {from_status.value} -> {to_status.value}"
            + (f" for order {order_id}" if order_id else "")
        )
        super().__init__(msg)


class OrderStateMachine:
    """Strict finite state machine for order lifecycle management.

    Enforces that every state transition follows the defined
    institutional order workflow. No bypass is allowed.

    Usage:
        sm = OrderStateMachine()
        order = Order(symbol="NVDA", ...)
        sm.transition(order, OrderStatus.VALIDATED)  # OK
        sm.transition(order, OrderStatus.FILLED)     # ERROR - not allowed from VALIDATED
    """

    # Valid transitions: from_status -> set of allowed to_status
    TRANSITIONS: Dict[OrderStatus, FrozenSet[OrderStatus]] = {
        OrderStatus.CREATED: frozenset({
            OrderStatus.VALIDATED,
            OrderStatus.CANCELLED,
        }),
        OrderStatus.VALIDATED: frozenset({
            OrderStatus.ROUTED,
            OrderStatus.REJECTED,
        }),
        OrderStatus.ROUTED: frozenset({
            OrderStatus.SUBMITTED,
            OrderStatus.REJECTED,
        }),
        OrderStatus.SUBMITTED: frozenset({
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }),
        OrderStatus.ACKNOWLEDGED: frozenset({
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
        }),
        OrderStatus.PARTIALLY_FILLED: frozenset({
            OrderStatus.PARTIALLY_FILLED,  # Allow incremental fills
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
        }),
        OrderStatus.FILLED: frozenset(),
        OrderStatus.CANCELLED: frozenset(),
        OrderStatus.REJECTED: frozenset(),
    }

    # Descriptive labels for each transition
    TRANSITION_LABELS: Dict[str, str] = {
        f"{OrderStatus.CREATED.value}->{OrderStatus.VALIDATED.value}": "Order validated",
        f"{OrderStatus.CREATED.value}->{OrderStatus.CANCELLED.value}": "Order cancelled before validation",
        f"{OrderStatus.VALIDATED.value}->{OrderStatus.ROUTED.value}": "Order routed to broker",
        f"{OrderStatus.VALIDATED.value}->{OrderStatus.REJECTED.value}": "Order rejected during validation",
        f"{OrderStatus.ROUTED.value}->{OrderStatus.SUBMITTED.value}": "Order submitted to exchange",
        f"{OrderStatus.ROUTED.value}->{OrderStatus.REJECTED.value}": "Order rejected by routing",
        f"{OrderStatus.SUBMITTED.value}->{OrderStatus.ACKNOWLEDGED.value}": "Order acknowledged by broker",
        f"{OrderStatus.SUBMITTED.value}->{OrderStatus.CANCELLED.value}": "Order cancelled while pending",
        f"{OrderStatus.SUBMITTED.value}->{OrderStatus.REJECTED.value}": "Order rejected by broker",
        f"{OrderStatus.ACKNOWLEDGED.value}->{OrderStatus.PARTIALLY_FILLED.value}": "Order partially filled",
        f"{OrderStatus.ACKNOWLEDGED.value}->{OrderStatus.FILLED.value}": "Order fully filled",
        f"{OrderStatus.ACKNOWLEDGED.value}->{OrderStatus.CANCELLED.value}": "Order cancelled",
        f"{OrderStatus.PARTIALLY_FILLED.value}->{OrderStatus.PARTIALLY_FILLED.value}": "Additional partial fill",
        f"{OrderStatus.PARTIALLY_FILLED.value}->{OrderStatus.FILLED.value}": "Order fully filled",
        f"{OrderStatus.PARTIALLY_FILLED.value}->{OrderStatus.CANCELLED.value}": "Remaining order cancelled",
    }

    def can_transition(self, from_status: OrderStatus, to_status: OrderStatus) -> bool:
        """Check if a transition is valid without performing it.

        Args:
            from_status: Current order status
            to_status: Desired target status

        Returns:
            True if the transition is allowed
        """
        allowed = self.TRANSITIONS.get(from_status, frozenset())
        return to_status in allowed

    def validate_transition(self, from_status: OrderStatus, to_status: OrderStatus, order_id: str = "") -> None:
        """Validate a transition, raising an error if invalid.

        Args:
            from_status: Current order status
            to_status: Desired target status
            order_id: Optional order ID for error messages

        Raises:
            InvalidTransitionError: If the transition is not allowed
        """
        if not self.can_transition(from_status, to_status):
            raise InvalidTransitionError(from_status, to_status, order_id)

    def transition(self, order: Order, to_status: OrderStatus) -> Order:
        """Execute a state transition on an order.

        Validates the transition, records it in history,
        and updates the order's status and timestamp.

        Args:
            order: The order to transition
            to_status: Target status

        Returns:
            The updated order (modified in-place)

        Raises:
            InvalidTransitionError: If the transition is not allowed
        """
        from_status = order.status

        # Allow same-state transition only for PARTIALLY_FILLED (incremental fills)
        if from_status == to_status and to_status != OrderStatus.PARTIALLY_FILLED:
            raise InvalidTransitionError(from_status, to_status, order.order_id)

        self.validate_transition(from_status, to_status, order.order_id)

        old_status = order.status
        order.status = to_status
        order.updated_at = order.updated_at.__class__.utcnow()
        order.record_status_change(old_status, to_status)

        # Set milestone timestamps
        if to_status == OrderStatus.SUBMITTED and order.submitted_at is None:
            order.submitted_at = order.updated_at
        elif to_status == OrderStatus.FILLED and order.filled_at is None:
            order.filled_at = order.updated_at
        elif to_status == OrderStatus.CANCELLED and order.cancelled_at is None:
            order.cancelled_at = order.updated_at

        return order

    def get_allowed_transitions(self, status: OrderStatus) -> Set[OrderStatus]:
        """Get all valid next states from a given status.

        Args:
            status: Current order status

        Returns:
            Set of allowed next status values
        """
        return set(self.TRANSITIONS.get(status, frozenset()))

    def get_transition_label(self, from_status: OrderStatus, to_status: OrderStatus) -> str:
        """Get a human-readable label for a transition.

        Args:
            from_status: Source status
            to_status: Target status

        Returns:
            Human-readable description of the transition
        """
        key = f"{from_status.value}->{to_status.value}"
        return self.TRANSITION_LABELS.get(key, f"Unknown transition: {from_status.value} -> {to_status.value}")

    def is_terminal(self, status: OrderStatus) -> bool:
        """Check if a status is terminal (no further transitions allowed).

        Args:
            status: Order status to check

        Returns:
            True if no transitions are possible from this status
        """
        return len(self.TRANSITIONS.get(status, frozenset())) == 0

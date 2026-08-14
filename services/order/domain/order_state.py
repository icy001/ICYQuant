"""Order state machine (Commit 33 Part 1.1).

Legal transitions::

    CREATED          -> PENDING_SUBMIT
    PENDING_SUBMIT   -> SUBMITTED / REJECTED
    SUBMITTED        -> ACCEPTED / REJECTED
    ACCEPTED         -> PARTIALLY_FILLED / FILLED / CANCEL_PENDING / EXPIRED
    PARTIALLY_FILLED -> PARTIALLY_FILLED / FILLED / CANCEL_PENDING
    CANCEL_PENDING   -> CANCELLED
    FILLED / CANCELLED / REJECTED / EXPIRED -> (terminal)

An order can never jump from CREATED straight to FILLED: it must walk the
canonical lifecycle exactly.
"""

from __future__ import annotations

from typing import FrozenSet, Mapping

from services.order.domain.order_status import OrderStatus


class InvalidOrderStateTransition(ValueError):
    """Raised when an order status transition is not allowed."""


_TRANSITIONS: Mapping[OrderStatus, FrozenSet[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.PENDING_SUBMIT}),
    OrderStatus.PENDING_SUBMIT: frozenset(
        {OrderStatus.SUBMITTED, OrderStatus.REJECTED}
    ),
    OrderStatus.SUBMITTED: frozenset(
        {OrderStatus.ACCEPTED, OrderStatus.REJECTED}
    ),
    OrderStatus.ACCEPTED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
        }
    ),
    OrderStatus.CANCEL_PENDING: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
}


class OrderStateMachine:
    """Guards every legal order status transition.

    ``transition`` returns the target status; anything outside the table above
    raises :class:`InvalidOrderStateTransition` (fail-closed: an unknown or
    illegal move is never silently accepted).
    """

    transitions: Mapping[OrderStatus, FrozenSet[OrderStatus]] = _TRANSITIONS

    def can_transition(
        self,
        current: OrderStatus,
        target: OrderStatus,
    ) -> bool:
        return target in self.transitions.get(current, frozenset())

    def transition(
        self,
        current: OrderStatus,
        target: OrderStatus,
    ) -> OrderStatus:
        if not self.can_transition(current, target):
            raise InvalidOrderStateTransition(
                f"invalid order state transition: {current.value} -> {target.value}"
            )
        return target

"""Order lifecycle service (Commit 33 Part 1.2).

Wraps the domain :class:`~services.order.domain.order_state.OrderStateMachine`
together with validation so that every state change is guarded:

* transitions are only performed through the state machine (never
  ``order.status = ...``)
* every transition is validated first (fail-closed)
* every transition returns a new immutable order with ``status`` and
  ``updated_at`` moved - ``created_at`` and the authorization lineage never
  change (Commit 33 Part 1.2 #20 / #29)
* repeated commands for an already-reached state are idempotent no-ops
  (Commit 33 Part 1.2 #26 / #27)

Commands are two-phase where the real market demands it: a cancel request only
moves ACCEPTED/PARTIALLY_FILLED -> CANCEL_PENDING; the downstream confirmation
later moves CANCEL_PENDING -> CANCELLED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from services.order.domain.order import Order
from services.order.domain.order_state import OrderStateMachine
from services.order.domain.order_status import OrderStatus
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.validator import (
    OrderValidationError,
    OrderValidator,
)


class OrderLifecycle:
    """Guarded state transitions for an order."""

    def __init__(
        self,
        *,
        state_machine: Optional[OrderStateMachine] = None,
        validator: Optional[OrderValidator] = None,
    ) -> None:
        self._state_machine = state_machine or OrderStateMachine()
        self._validator = validator or OrderValidator()

    @property
    def state_machine(self) -> OrderStateMachine:
        return self._state_machine

    def submit(self, order: Order, *, at: Optional[datetime] = None) -> Order:
        """CREATED -> PENDING_SUBMIT (engine's submit boundary)."""
        return self._transition(order, OrderStatus.PENDING_SUBMIT, at=at)

    def submit_to_venue(
        self,
        order: Order,
        *,
        at: Optional[datetime] = None,
    ) -> Order:
        """PENDING_SUBMIT -> SUBMITTED (the order enters the execution channel).

        This is where the execution adapter takes over (Commit 33 Part 1.3
        #13): the engine keeps the order durable at SUBMITTED while the
        gateway talks to the venue.
        """
        return self._transition(order, OrderStatus.SUBMITTED, at=at)

    def accept(self, order: Order, *, at: Optional[datetime] = None) -> Order:
        """SUBMITTED -> ACCEPTED (downstream confirmation)."""
        return self._transition(order, OrderStatus.ACCEPTED, at=at)

    def reject(
        self,
        order: Order,
        reason: str,
        *,
        at: Optional[datetime] = None,
    ) -> Order:
        """-> REJECTED; the rejection reason is always recorded (#21)."""
        if order.status is OrderStatus.REJECTED:
            return order  # idempotent no-op
        self._validate(order)
        self._state_machine.transition(order.status, OrderStatus.REJECTED)
        return order.with_reject(reason, at=at)

    def cancel(self, order: Order, *, at: Optional[datetime] = None) -> Order:
        """ACCEPTED/PARTIALLY_FILLED -> CANCEL_PENDING (request, not result)."""
        return self._transition(order, OrderStatus.CANCEL_PENDING, at=at)

    def expire(self, order: Order, *, at: Optional[datetime] = None) -> Order:
        """ACCEPTED -> EXPIRED, only when the TimeInForce allows it (#8)."""
        if order.status is OrderStatus.EXPIRED:
            return order  # idempotent no-op
        if order.time_in_force is not TimeInForce.DAY:
            raise OrderValidationError(
                f"{order.time_in_force.value} order cannot expire"
            )
        self._validate(order)
        self._state_machine.transition(order.status, OrderStatus.EXPIRED)
        return order.with_status(OrderStatus.EXPIRED, at=at)

    def _transition(
        self,
        order: Order,
        target: OrderStatus,
        *,
        at: Optional[datetime] = None,
    ) -> Order:
        if order.status is target:
            return order  # idempotent no-op
        self._validate(order)
        self._state_machine.transition(order.status, target)
        return order.with_status(target, at=at)

    def _validate(self, order: Order) -> None:
        self._validator.validate(order)

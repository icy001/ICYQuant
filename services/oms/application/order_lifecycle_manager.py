"""OrderLifecycleManager — single entry point for all order state changes.

All order lifecycle operations (accept, create, route, working,
apply_execution, cancel, expire, reject, fail) go through this manager.
No other code should directly mutate order.status.

The manager enforces:
    - State machine validation
    - Terminal state protection
    - Event generation for every transition
    - Quantity invariants on fills
    - Unknown-execution-state handling (not auto-FAILED)
"""
from __future__ import annotations

import time
from typing import Any, Optional

from services.oms.domain.order import Order
from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import (
    OrderLifecycleEvent,
    LifecycleEventType,
)
from services.oms.errors.order_errors import (
    OrderNotFoundError,
    ConcurrentModificationError,
    OrderQuantityInconsistencyError,
)
from services.oms.errors.lifecycle_errors import (
    InvalidStateTransitionError,
    TerminalStateModificationError,
    UnknownExecutionStateError,
)
from .order_state_machine import OrderStateMachine


class OrderLifecycleManager:
    """Manages the lifecycle of OMS orders.

    Every method:
      1. Validates the current state allows the transition.
      2. Applies the state machine transition.
      3. Appends a lifecycle event with full audit context.
      4. Updates order metadata (version, timestamp, quantities).

    Returns the mutated Order (for chaining).
    """

    def __init__(self, actor: str = "oms-lifecycle",
                 actor_type: str = "OMS") -> None:
        self.actor = actor
        self.actor_type = actor_type

    # ── Lifecycle progression ──────────────────────

    def create(self, order: Order,
               expected_version: Optional[int] = None) -> Order:
        """ACCEPTED → CREATED."""
        return self._transition(
            order, LifecycleEventType.ORDER_CREATED,
            expected_version=expected_version,
            reason="Order created",
        )

    def route(self, order: Order,
              expected_version: Optional[int] = None) -> Order:
        """CREATED → ROUTING."""
        return self._transition(
            order, LifecycleEventType.ORDER_ROUTING_STARTED,
            expected_version=expected_version,
            reason="Routing started",
        )

    def working(self, order: Order,
                expected_version: Optional[int] = None) -> Order:
        """ROUTING → WORKING."""
        return self._transition(
            order, LifecycleEventType.ORDER_WORKING,
            expected_version=expected_version,
            reason="Order working at venue",
        )

    # ── Execution ──────────────────────────────────

    def apply_execution(self, order: Order,
                        fill_quantity: float,
                        fill_price: float = 0.0,
                        execution_id: str = "",
                        expected_version: Optional[int] = None) -> Order:
        """Apply an execution fill to an order.

        WORKING or PARTIALLY_FILLED → PARTIALLY_FILLED or FILLED.
        """
        if fill_quantity <= 0:
            raise ValueError("Fill quantity must be positive")

        if fill_quantity > order.quantity.remaining:
            raise OrderQuantityInconsistencyError(
                order.order_id.order_id,
                filled=order.quantity.filled + fill_quantity,
                remaining=0,
                cancelled=order.quantity.cancelled,
                original=order.quantity.original,
            )

        # Apply fill to quantity tracker
        order.apply_fill(fill_quantity, fill_price)

        # Determine next state
        if order.quantity.remaining <= 0:
            event_type = LifecycleEventType.ORDER_FILLED
        else:
            event_type = LifecycleEventType.ORDER_PARTIAL_FILL

        return self._transition(
            order, event_type,
            expected_version=expected_version,
            reason=f"Execution {execution_id}",
            execution_id=execution_id,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            filled_quantity=order.quantity.filled,
            remaining_quantity=order.quantity.remaining,
        )

    # ── Cancel (two-phase: REQUESTED → CONFIRMED → CANCELLED) ──

    def request_cancel(self, order: Order,
                       reason: str = "",
                       expected_version: Optional[int] = None) -> Order:
        """Request cancellation. Order stays WORKING until confirmed."""
        return self._transition(
            order, LifecycleEventType.ORDER_CANCEL_REQUESTED,
            expected_version=expected_version,
            reason=reason or "Cancel requested",
        )

    def confirm_cancel(self, order: Order,
                       reason: str = "",
                       expected_version: Optional[int] = None) -> Order:
        """Confirm cancellation. Cancels remaining quantity."""
        order.quantity.cancel_remaining()
        return self._transition(
            order, LifecycleEventType.ORDER_CANCEL_CONFIRMED,
            expected_version=expected_version,
            reason=reason or "Cancel confirmed",
            cancelled_quantity=order.quantity.cancelled,
        )

    def cancel(self, order: Order,
               reason: str = "",
               expected_version: Optional[int] = None) -> Order:
        """Immediate cancel (for non-working states)."""
        order.quantity.cancel_remaining()
        return self._transition(
            order, LifecycleEventType.ORDER_CANCELLED,
            expected_version=expected_version,
            reason=reason or "Order cancelled",
            cancelled_quantity=order.quantity.cancelled,
        )

    # ── Reject ─────────────────────────────────────

    def reject(self, order: Order,
               reason: str = "",
               expected_version: Optional[int] = None) -> Order:
        """Reject an order (execution reject — order already exists)."""
        return self._transition(
            order, LifecycleEventType.ORDER_REJECTED,
            expected_version=expected_version,
            reason=reason or "Order rejected",
        )

    # ── Expire ─────────────────────────────────────

    def expire(self, order: Order,
               expected_version: Optional[int] = None) -> Order:
        """Expire an order whose expires_at has passed."""
        return self._transition(
            order, LifecycleEventType.ORDER_EXPIRED,
            expected_version=expected_version,
            reason="Order expired",
            expires_at=order.expires_at,
        )

    def check_expiration(self, order: Order) -> Optional[Order]:
        """If the order has expired, transition it to EXPIRED.

        Returns the order if it was expired, None otherwise.
        """
        if not order.needs_expiration_check:
            return None
        return self.expire(order)

    # ── Fail ───────────────────────────────────────

    def fail(self, order: Order,
             reason: str = "",
             expected_version: Optional[int] = None) -> Order:
        """Mark an order as FAILED.

        NOTE: This should only be used for confirmed failures.
        For unknown execution states, use mark_unknown().
        """
        return self._transition(
            order, LifecycleEventType.ORDER_FAILED,
            expected_version=expected_version,
            reason=reason or "Order failed",
        )

    # ── Unknown execution state ────────────────────

    def mark_unknown(self, order: Order,
                     execution_id: str = "",
                     expected_version: Optional[int] = None) -> Order:
        """Mark an order as having an unknown execution state.

        The order STAYS in its current status (e.g. WORKING) but
        sets the execution_status_unknown flag. This prevents
        incorrect transition to FAILED when the execution result
        is ambiguous (e.g. network timeout).

        Subsequent Execution Reconciliation will resolve the state.
        """
        if order.status.is_terminal:
            raise TerminalStateModificationError(
                order.order_id.order_id, order.status,
            )
        order.execution_status_unknown = True
        order.updated_at = time.time()
        if expected_version is not None:
            self._check_version(order, expected_version)
        order.version += 1
        return order

    # ── Internal ───────────────────────────────────

    def _transition(self, order: Order,
                    event_type: LifecycleEventType,
                    expected_version: Optional[int] = None,
                    reason: str = "",
                    **payload: Any) -> Order:
        """Execute a state transition through the state machine."""
        if expected_version is not None:
            self._check_version(order, expected_version)

        # Use the state machine to validate and get next status
        new_status = OrderStateMachine.transition(
            order.status, event_type, order.order_id.order_id,
        )

        # Build the lifecycle event
        event = OrderLifecycleEvent.create(
            event_type=event_type,
            order_id=order.order_id.order_id,
            previous_status=order.status,
            lineage_id=order.lineage_id,
            certificate_id=order.certificate_id,
            actor=self.actor,
            actor_type=self.actor_type,
            reason=reason,
            **payload,
        )

        # Apply event — lifecycle.append will also validate
        order.apply_event(event)
        order.status = new_status
        order.version += 1
        order.updated_at = time.time()
        return order

    @staticmethod
    def _check_version(order: Order, expected_version: int) -> None:
        if order.version != expected_version:
            raise ConcurrentModificationError(
                order.order_id.order_id,
                expected_version=expected_version,
                actual_version=order.version,
            )

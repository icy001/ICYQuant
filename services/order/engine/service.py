"""Order engine service (Commit 33 Part 1.2).

The application boundary for everything an order does.  Business code no
longer talks to :class:`~services.order.engine.factory.OrderFactory`,
:class:`~services.order.engine.lifecycle.OrderLifecycle` or the repository
directly - it goes through :class:`OrderEngineService`:

.. code-block:: text

    Order Request (HANDOFF)
        -> OrderEngineService
             |-- Validate
             |-- Create
             |-- Persist
             `-- Transition
        -> Order

Reliability rules enforced here:

* create follows Validate -> Create -> Persist -> Return; a persist failure
  means the order was never created (fail-closed, #18)
* every state change is persisted before it is returned (#19)
* repeated submit / accept / cancel are idempotent no-ops (#26 / #27)
* invalid transitions raise
  :class:`~services.order.domain.order_state.InvalidOrderStateTransition`
* the service never touches Position / Ledger - fills and positions are built
  from execution events downstream (#25)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from services.order.domain.order import Order
from services.order.domain.order_status import OrderStatus
from services.order.engine.command import (
    AcceptOrderCommand,
    CancelOrderCommand,
    CreateOrderCommand,
    ExpireOrderCommand,
    RejectOrderCommand,
    SubmitOrderCommand,
)
from services.order.engine.execution.adapter import ExecutionAdapter
from services.order.engine.execution.gateway import FakeExecutionGateway
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)
from services.order.engine.factory import OrderFactory
from services.order.engine.lifecycle import OrderLifecycle
from services.order.engine.repository import (
    InMemoryOrderRepository,
    OrderRepository,
)
from services.order.engine.validator import OrderValidator

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.order.request.normalization import NormalizedOrderRequest
    from services.order.request.repository import OrderRequestSnapshot


class OrderNotFoundError(KeyError):
    """Raised when a command references an unknown order id."""


class OrderEngineService:
    """Unified boundary for creating and transitioning orders."""

    def __init__(
        self,
        *,
        factory: Optional[OrderFactory] = None,
        validator: Optional[OrderValidator] = None,
        lifecycle: Optional[OrderLifecycle] = None,
        repository: Optional[OrderRepository] = None,
        adapter: Optional[ExecutionAdapter] = None,
    ) -> None:
        self._factory = factory or OrderFactory()
        self._validator = validator or OrderValidator()
        self._lifecycle = lifecycle or OrderLifecycle()
        self._repository = repository or InMemoryOrderRepository()
        self._adapter = adapter or ExecutionAdapter(FakeExecutionGateway())

    def create(
        self,
        request: "OrderRequestSnapshot | NormalizedOrderRequest",
        command: CreateOrderCommand,
    ) -> Order:
        """Validate -> create -> persist -> return (fail-closed)."""
        self._validator.validate_request(request)
        order = self._factory.create(request, command)
        self._validator.validate(order)
        self._repository.save(order)
        return order

    def submit(self, command: SubmitOrderCommand) -> Order:
        """Drive the order through the execution boundary (Part 1.3).

        CREATED -> PENDING_SUBMIT -> SUBMITTED, then the adapter sends the
        order to the gateway and the response is mapped back:

        * ACCEPTED -> Order ACCEPTED (+ venue_order_id)
        * REJECTED -> Order REJECTED (+ reject_reason)
        * PENDING / UNKNOWN -> Order stays SUBMITTED (query before retry)

        The SUBMITTED state is persisted *before* the external call: if the
        gateway is unavailable the engine stops - it never fakes an ACCEPTED
        or a FILLED (fail-closed, #26).  Orders already past submission are a
        no-op.
        """
        order = self._load(command.order_id)
        if order.status not in (
            OrderStatus.CREATED,
            OrderStatus.PENDING_SUBMIT,
        ):
            return order  # idempotent: already inside/after the submit flow

        pending = self._lifecycle.submit(order, at=command.timestamp)
        submitted = self._lifecycle.submit_to_venue(pending, at=command.timestamp)
        self._persist(submitted, order)

        response = self._adapter.submit(submitted)
        final = self._apply_execution_response(submitted, response)
        return self._persist(final, submitted)

    def _apply_execution_response(
        self,
        submitted: Order,
        response: ExecutionResponse,
    ) -> Order:
        """Map an execution response onto the order state (Commit 33 #14)."""
        if response.status is ExecutionResponseStatus.ACCEPTED:
            accepted = self._lifecycle.accept(submitted, at=response.timestamp)
            if response.venue_order_id:
                return accepted.with_venue_order_id(
                    response.venue_order_id,
                    at=response.timestamp,
                )
            return accepted
        if response.status is ExecutionResponseStatus.REJECTED:
            reason = response.reject_reason or "EXECUTION_REJECTED"
            return self._lifecycle.reject(submitted, reason, at=response.timestamp)
        # PENDING / UNKNOWN: keep SUBMITTED and wait for query/reconciliation.
        return submitted

    def accept(self, command: AcceptOrderCommand) -> Order:
        """SUBMITTED -> ACCEPTED (idempotent)."""
        order = self._load(command.order_id)
        updated = self._lifecycle.accept(order, at=command.timestamp)
        return self._persist(updated, order)

    def reject(self, command: RejectOrderCommand) -> Order:
        """-> REJECTED with the recorded reason (idempotent)."""
        order = self._load(command.order_id)
        updated = self._lifecycle.reject(
            order,
            command.reason,
            at=command.timestamp,
        )
        return self._persist(updated, order)

    def cancel(self, command: CancelOrderCommand) -> Order:
        """ACCEPTED/PARTIALLY_FILLED -> CANCEL_PENDING (idempotent)."""
        order = self._load(command.order_id)
        updated = self._lifecycle.cancel(order, at=command.timestamp)
        return self._persist(updated, order)

    def expire(self, command: ExpireOrderCommand) -> Order:
        """ACCEPTED -> EXPIRED (idempotent, TimeInForce-guarded)."""
        order = self._load(command.order_id)
        updated = self._lifecycle.expire(order, at=command.timestamp)
        return self._persist(updated, order)

    def _load(self, order_id: str) -> Order:
        order = self._repository.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"order not found: {order_id}")
        return order

    def _persist(self, updated: Order, original: Order) -> Order:
        if updated is not original:  # not an idempotent no-op
            self._repository.update(updated)
        return updated

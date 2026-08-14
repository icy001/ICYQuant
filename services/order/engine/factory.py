"""Order factory (Commit 33 Part 1.1 / 1.2).

The :class:`OrderFactory` is the only boundary where a handoff order request
becomes an :class:`~services.order.domain.order.Order`:

.. code-block:: text

    NormalizedOrderRequest (HANDOFF)
        -> CreateOrderCommand
        -> OrderFactory
        -> Order (CREATED)

The factory copies the normalized trading parameters and the complete
authorization lineage but never re-runs risk evaluation: max position, order
size ceilings and exposure were already decided by the risk engine (Commit
31).  The engine accepts already-authorized requests - it does not re-decide
whether a strategy should trade.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from services.order.domain.identifiers import new_order_id
from services.order.domain.order import Order
from services.order.domain.order_side import OrderSide
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.command import CreateOrderCommand
from services.order.request.state import OrderRequestState

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.order.request.normalization import NormalizedOrderRequest
    from services.order.request.repository import OrderRequestSnapshot


class OrderCreationError(ValueError):
    """Raised when an order cannot be created from the given request."""


class OrderFactory:
    """Builds orders exclusively from HANDOFF order requests.

    Domain preconditions enforced here (fail-closed):

    * the request exists and is in ``HANDOFF`` state (never CREATED / VALIDATED)
    * the command targets the same order request
    * LIMIT requires a positive ``limit_price``; MARKET forbids one
    * quantity is positive
    * quantity and price are converted to exact :class:`~decimal.Decimal`
    """

    def create(
        self,
        request: "OrderRequestSnapshot | NormalizedOrderRequest",
        command: CreateOrderCommand,
    ) -> Order:
        if request is None:
            raise OrderCreationError("handoff order request is required")
        if command is None:
            raise OrderCreationError("create order command is required")
        if command.order_request_id != request.order_request_id:
            raise OrderCreationError(
                "create order command targets a different order request"
            )

        state = getattr(request, "state", None)
        if state != OrderRequestState.HANDOFF:
            raise OrderCreationError(
                "order can only be created from a HANDOFF order request"
            )

        order_type = OrderType(request.order_type.strip().upper())
        limit_price = self._to_decimal(request.limit_price)
        if order_type is OrderType.LIMIT:
            if limit_price is None or limit_price <= 0:
                raise OrderCreationError(
                    "LIMIT order requires a positive limit_price"
                )
        else:  # MARKET
            if limit_price is not None:
                raise OrderCreationError("MARKET order cannot have a limit_price")

        quantity = self._to_decimal(request.quantity)
        if quantity is None or quantity <= 0:
            raise OrderCreationError("order quantity must be positive")

        created_at = self._to_datetime(request.created_at)
        return Order(
            order_id=new_order_id(request.created_at),
            order_request_id=request.order_request_id,
            client_order_id=command.client_order_id,
            intent_id=request.intent_id,
            authorization_id=request.authorization_id,
            certificate_id=request.certificate_id,
            decision_id=request.decision_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            symbol=request.symbol,
            side=OrderSide(request.side.strip().upper()),
            quantity=quantity,
            order_type=order_type,
            time_in_force=TimeInForce(request.time_in_force.strip().upper()),
            limit_price=limit_price,
            status=OrderStatus.CREATED,
            created_at=created_at,
            updated_at=command.timestamp,
        )

    @staticmethod
    def _to_decimal(value: object) -> Optional[Decimal]:
        """Exact Decimal conversion - never binary float, never ``0.1+0.2``.

        ``Decimal(str(...))`` keeps the printed precision; ``Decimal(0.1)``
        would keep the binary float's full expansion.
        """
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _to_datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromtimestamp(float(value))

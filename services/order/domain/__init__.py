"""Order domain model (Commit 33 Part 1.1 / 1.4).

The OMS core: an :class:`~services.order.domain.order.Order` is the formal
trading order created from a HANDOFF order request.  This package is the pure
domain - no persistence, no adapters.  The engine package
(``services.order.engine``) builds and transitions orders from here, and the
:mod:`~services.order.domain.events` package records why each state changed.
"""

from services.order.domain.events import (
    OrderAccepted,
    OrderCancelPending,
    OrderCancelled,
    OrderCreated,
    OrderEvent,
    OrderExpired,
    OrderRejected,
    OrderSubmitted,
)
from services.order.domain.identifiers import (
    CLIENT_ORDER_ID_PREFIX,
    EVENT_ID_PREFIX,
    EXECUTION_ID_PREFIX,
    EXECUTION_REQUEST_ID_PREFIX,
    ORDER_ID_PREFIX,
    new_client_order_id,
    new_event_id,
    new_execution_id,
    new_execution_request_id,
    new_order_id,
)
from services.order.domain.order import Order
from services.order.domain.order_side import OrderSide
from services.order.domain.order_state import (
    InvalidOrderStateTransition,
    OrderStateMachine,
)
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce

__all__ = [
    "CLIENT_ORDER_ID_PREFIX",
    "EVENT_ID_PREFIX",
    "EXECUTION_ID_PREFIX",
    "EXECUTION_REQUEST_ID_PREFIX",
    "ORDER_ID_PREFIX",
    "InvalidOrderStateTransition",
    "Order",
    "OrderAccepted",
    "OrderCancelPending",
    "OrderCancelled",
    "OrderCreated",
    "OrderEvent",
    "OrderExpired",
    "OrderRejected",
    "OrderSide",
    "OrderStateMachine",
    "OrderStatus",
    "OrderSubmitted",
    "OrderType",
    "TimeInForce",
    "new_client_order_id",
    "new_event_id",
    "new_execution_id",
    "new_execution_request_id",
    "new_order_id",
]

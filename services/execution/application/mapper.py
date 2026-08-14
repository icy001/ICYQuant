"""Order -> Execution boundary mapper (Commit 38 Part 1.1).

The Execution Engine never reads a Strategy Signal or an OMS ``Order``
directly.  This module is the single place that translates the OMS order
vocabulary into the Execution vocabulary:

.. code-block:: text

    Order.side       -> ExecutionSide
    Order.order_type -> ExecutionOrderType
    Order            -> ExecutionRequest

Keeping the mapping here means Broker / Exchange / FIX / REST / WebSocket /
DMA / Paper / Simulator adapters never pollute the Strategy or OMS domain.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionSide,
)
from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType


def order_side_to_execution_side(
    side: OrderSide,
) -> ExecutionSide:
    """Map an OMS order side to its execution side.

    The OMS and Execution vocabularies both use BUY / SELL; the mapping
    exists to keep the boundary explicit and to guard the Execution domain
    against position-style vocabulary (LONG / SHORT).
    """
    return ExecutionSide(side.value)


def order_type_to_execution_type(
    order_type: OrderType,
) -> ExecutionOrderType:
    """Map an OMS order type to its execution type.

    The OMS domain currently supports MARKET / LIMIT.  STOP / STOP_LIMIT are
    part of the Execution vocabulary but have no OMS equivalent yet - the
    factory accepts them directly.
    """
    return ExecutionOrderType(order_type.value)


def execution_request_from_order(order: Any) -> ExecutionRequest:
    """Build an ``ExecutionRequest`` from an OMS ``Order`` (duck typed).

    Only the fields the Execution Engine needs are carried across:
    ``order_id``, ``symbol``, ``side``, ``order_type``, ``quantity`` and
    ``limit_price``.  ``quantity`` / ``limit_price`` are Decimals in the OMS
    and are normalized to ``float`` here.

    The returned request is validated and therefore always in
    ``ExecutionRequestStatus.CREATED``.
    """
    request = ExecutionRequest(
        request_id=str(uuid4()),
        order_id=order.order_id,
        symbol=order.symbol,
        side=order_side_to_execution_side(order.side),
        order_type=order_type_to_execution_type(order.order_type),
        quantity=float(order.quantity),
        price=(
            None
            if order.limit_price is None
            else float(order.limit_price)
        ),
        strategy_id=getattr(order, "strategy_id", None),
    )

    request.validate()

    return request

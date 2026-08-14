"""Execution adapter (Commit 33 Part 1.3).

The adapter is the mechanical bridge between the order domain and the gateway:

.. code-block:: text

    Order -> ExecutionRequest -> ExecutionGateway -> Venue
    ExecutionResponse -> (mapped by the order engine service)

It performs NO trading decisions: it never changes quantity, direction, price,
strategy or risk parameters (Commit 33 Part 1.3 #12).  Order splitting is a
future Execution Strategy concern and never happens here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from services.order.domain.identifiers import new_execution_request_id
from services.order.domain.order import Order
from services.order.engine.execution.contract import ExecutionGateway
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import ExecutionResponse


class ExecutionAdapter:
    """Builds execution requests from orders and drives the gateway."""

    def __init__(self, gateway: ExecutionGateway) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ExecutionGateway:
        return self._gateway

    def build_request(
        self,
        order: Order,
        *,
        execution_request_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> ExecutionRequest:
        """Derive the minimal immutable execution payload from an order.

        The order's authorization lineage is intentionally not copied: the
        execution layer can never modify the trading intent (#5).  A retry
        passes the previous ``execution_request_id`` as ``causation_id`` so
        the ``EXREQ-001 -> EXREQ-002`` chain stays traceable (#20).
        """
        return ExecutionRequest(
            execution_request_id=execution_request_id
            or new_execution_request_id(timestamp and timestamp.timestamp()),
            order_id=order.order_id,
            client_order_id=order.client_order_id or order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            time_in_force=order.time_in_force,
            limit_price=order.limit_price,
            correlation_id=order.correlation_id,
            causation_id=causation_id,
            timestamp=timestamp or order.updated_at,
        )

    def submit(self, order: Order) -> ExecutionResponse:
        """Submit an order to the venue through the gateway."""
        request = self.build_request(order)
        return self._gateway.submit(request)

    def cancel(self, order: Order) -> ExecutionResponse:
        """Request a cancellation through the gateway."""
        request = self.build_request(order)
        return self._gateway.cancel(request)

    def query(self, order_id: str) -> Optional[ExecutionResponse]:
        """Ask the gateway for the current venue state of an order."""
        return self._gateway.query(order_id)

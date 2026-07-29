"""Broker Adapter.

Translates between OMS internal models and broker-specific protocols.
Each adapter handles the conversion of order models to broker API
requests and maps broker responses back to OMS models.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..order.models import Order, OrderSide, OrderStatus, OrderType
from .broker_gateway import BrokerGateway, BrokerOrderRequest, BrokerOrderResponse


class BrokerAdapter:
    """Adapts OMS orders to broker-specific requests and back.

    Handles protocol translation between the OMS internal model
    and the broker gateway's request/response format.

    Usage:
        adapter = BrokerAdapter(gateway=paper_gateway)
        broker_request = adapter.to_broker_request(order)
        broker_response = await gateway.submit_order(broker_request)
        adapter.apply_fill(order, broker_response)
    """

    def __init__(self, gateway: BrokerGateway, account_id: str = "") -> None:
        self.gateway = gateway
        self.account_id = account_id

    def to_broker_request(self, order: Order) -> BrokerOrderRequest:
        """Convert an OMS Order to a broker order request.

        Args:
            order: OMS order

        Returns:
            Broker-compatible order request
        """
        return BrokerOrderRequest(
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            price=order.price,
            order_type=self._map_order_type(order.order_type),
            time_in_force=order.time_in_force.value,
            account_id=self.account_id,
            client_order_id=order.order_id,
            metadata={
                "strategy_id": order.strategy_id,
                "source": order.source.value,
                "tags": order.tags,
            },
        )

    def to_cancel_request(self, order: Order) -> BrokerOrderRequest:
        """Create a cancel request for an order.

        Args:
            order: OMS order to cancel

        Returns:
            Cancel request
        """
        return BrokerOrderRequest(
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.remaining_quantity,
            client_order_id=order.order_id,
            metadata={"action": "CANCEL"},
        )

    def apply_fill(
        self,
        order: Order,
        response: BrokerOrderResponse,
    ) -> Order:
        """Apply broker fill response to an OMS order.

        Args:
            order: OMS order to update
            response: Broker fill response

        Returns:
            Updated order (modified in-place)
        """
        if response.filled_quantity > 0:
            # Update average fill price
            total_value = (order.filled_quantity * order.average_fill_price) + (
                response.filled_quantity * response.average_price
            )
            order.filled_quantity += response.filled_quantity
            if order.filled_quantity > 0:
                order.average_fill_price = total_value / order.filled_quantity
            order.total_commission += response.commission

        return order

    def map_broker_status(self, broker_status: str) -> OrderStatus:
        """Map a broker status string to an OMS OrderStatus.

        Args:
            broker_status: Status string from broker

        Returns:
            Corresponding OMS OrderStatus
        """
        mapping: Dict[str, OrderStatus] = {
            "NEW": OrderStatus.SUBMITTED,
            "PENDING": OrderStatus.SUBMITTED,
            "ACKNOWLEDGED": OrderStatus.ACKNOWLEDGED,
            "ACCEPTED": OrderStatus.ACKNOWLEDGED,
            "PARTIAL": OrderStatus.PARTIALLY_FILLED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "COMPLETE": OrderStatus.FILLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "ERROR": OrderStatus.REJECTED,
        }
        return mapping.get(broker_status.upper(), OrderStatus.REJECTED)

    @staticmethod
    def _map_order_type(order_type: OrderType) -> str:
        """Map OMS order type to broker order type string.

        Args:
            order_type: OMS order type

        Returns:
            Broker order type string
        """
        return order_type.value

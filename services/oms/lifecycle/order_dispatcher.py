"""Order Dispatcher — Sends orders to broker gateways.

Handles the final dispatch step: sending the validated and routed
order to the broker gateway for submission to the exchange.

Pipeline:
    Routed Order → Gateway Selection → Protocol Encoding → Send → ACK Wait
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order

logger = logging.getLogger(__name__)


class DispatchStatus(str, Enum):
    """Dispatch result status."""
    SUCCESS = "success"
    FAILED = "failed"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"


@dataclass
class DispatchResult:
    """Result of dispatching an order."""
    order_id: str
    success: bool = False
    gateway: str = ""
    gateway_order_id: str = ""
    status: DispatchStatus = DispatchStatus.FAILED
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "success": self.success,
            "gateway": self.gateway,
            "gateway_order_id": self.gateway_order_id,
            "status": self.status.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class OrderDispatcher:
    """Dispatches orders to broker gateways.

    The final step before an order hits the exchange. Encodes orders
    in the appropriate protocol format and sends them to the gateway.

    In production, this integrates with FIX engine, REST API, or
    WebSocket connections. This implementation provides the interface
    and in-memory simulation for development.

    Usage::

        dispatcher = OrderDispatcher()
        dispatcher.register_gateway("IB_FIX", endpoint="fix://ib-gateway:4000")
        result = await dispatcher.dispatch(order)
        if result.success:
            print(f"Order dispatched: {result.gateway_order_id}")
    """

    def __init__(self) -> None:
        # gateway_id → GatewayConfig
        self._gateways: dict[str, GatewayConfig] = {}
        # Counter for simulated gateway order IDs
        self._counter: int = 0

    async def dispatch(self, order: Order) -> DispatchResult:
        """Dispatch an order to the appropriate gateway.

        Args:
            order: Order to dispatch (must have broker/route set)

        Returns:
            DispatchResult with gateway info and order ID
        """
        # Determine target gateway
        gateway_id = order.broker or "default"
        gateway = self._gateways.get(gateway_id)

        if gateway is None:
            # Try any available gateway
            if self._gateways:
                gateway_id = next(iter(self._gateways))
                gateway = self._gateways[gateway_id]
                logger.warning(
                    f"No gateway for broker '{order.broker}', "
                    f"falling back to {gateway_id}"
                )
            else:
                return DispatchResult(
                    order_id=order.order_id,
                    status=DispatchStatus.GATEWAY_UNAVAILABLE,
                    reason="No gateways registered",
                )

        # Simulate dispatch (in production, this sends via FIX/REST)
        self._counter += 1
        gateway_order_id = f"GW-{gateway_id}-{self._counter:08d}"

        order.submitted_at = datetime.now(timezone.utc)

        logger.info(
            f"Order {order.order_id} dispatched to {gateway_id}: "
            f"{order.symbol} {order.side.value} qty={order.quantity} "
            f"gateway_order_id={gateway_order_id}"
        )

        return DispatchResult(
            order_id=order.order_id,
            success=True,
            gateway=gateway_id,
            gateway_order_id=gateway_order_id,
            status=DispatchStatus.SUCCESS,
            reason=f"Dispatched to {gateway_id}",
            metadata={
                "broker": order.broker,
                "market": order.market,
                "gateway_endpoint": gateway.endpoint,
            },
        )

    def register_gateway(
        self,
        gateway_id: str,
        endpoint: str = "",
        protocol: str = "FIX",
        **kwargs: Any,
    ) -> None:
        """Register a broker gateway.

        Args:
            gateway_id: Unique gateway identifier (typically broker name)
            endpoint: Gateway connection endpoint
            protocol: Communication protocol (FIX, REST, WS)
            **kwargs: Additional gateway configuration
        """
        self._gateways[gateway_id] = GatewayConfig(
            gateway_id=gateway_id,
            endpoint=endpoint,
            protocol=protocol,
            metadata=kwargs,
        )
        logger.info(f"Registered gateway: {gateway_id} ({protocol}: {endpoint})")

    def is_gateway_available(self, gateway_id: str) -> bool:
        """Check if a gateway is registered.

        Args:
            gateway_id: Gateway identifier

        Returns:
            True if the gateway is available
        """
        return gateway_id in self._gateways

    def to_dict(self) -> dict[str, Any]:
        """Serialize dispatcher state."""
        return {
            "gateways": {
                gid: g.to_dict() for gid, g in self._gateways.items()
            },
            "dispatch_count": self._counter,
        }


@dataclass
class GatewayConfig:
    """Configuration for a broker gateway connection."""
    gateway_id: str
    endpoint: str = ""
    protocol: str = "FIX"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "metadata": self.metadata,
        }

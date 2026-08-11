"""Broker Gateway — Unified broker connection and order management.

Provides a uniform interface for interacting with different brokers,
abstracting away protocol differences (FIX, REST, WebSocket, gRPC).

Pipeline::

    EMS → BrokerGateway.submit() → BrokerAdapter → Exchange

Usage::

    gateway = BrokerGateway("PRIMARY", adapter)
    await gateway.connect(credentials)
    result = await gateway.submit_order(order_request)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.execution_gateway.broker_adapter import BrokerAdapter
from services.execution_gateway.metrics import GatewayMetrics

logger = logging.getLogger(__name__)


class GatewayStatus(str, Enum):
    """Broker gateway connection status."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class BrokerGateway:
    """Unified broker gateway for order submission and management.

    Encapsulates broker-specific communication details behind a
    consistent interface.

    Attributes:
        name: Broker identifier
        adapter: Broker-specific adapter
        status: Connection status
        session_id: Current session identifier
        connected_at: Connection timestamp
        _credentials: Authentication credentials
        _metrics: Gateway metrics
    """

    def __init__(
        self,
        name: str,
        adapter: Optional[BrokerAdapter] = None,
        metrics: Optional[GatewayMetrics] = None,
    ) -> None:
        self.name = name
        self.adapter = adapter
        self.status = GatewayStatus.DISCONNECTED
        self.session_id: str = ""
        self.connected_at: Optional[datetime] = None
        self._credentials: dict[str, Any] = {}
        self._metrics = metrics or GatewayMetrics()

    # ── Connection ─────────────────────────────────────────────────

    async def connect(self, **credentials) -> bool:
        """Connect to the broker.

        Args:
            **credentials: Authentication credentials

        Returns:
            True if connected successfully
        """
        self.status = GatewayStatus.CONNECTING
        self._credentials = credentials
        logger.info("Connecting to broker %s...", self.name)

        try:
            self.session_id = str(uuid.uuid4())
            self.connected_at = datetime.now(timezone.utc)
            self.status = GatewayStatus.CONNECTED
            self._metrics.record_fix_session("CONNECTED")

            logger.info("Connected to broker %s (session=%s)", self.name, self.session_id)
            return True
        except Exception as e:
            self.status = GatewayStatus.ERROR
            logger.error("Failed to connect to broker %s: %s", self.name, e)
            return False

    async def disconnect(self) -> bool:
        """Disconnect from the broker.

        Returns:
            True if disconnected
        """
        logger.info("Disconnecting from broker %s", self.name)
        self.status = GatewayStatus.DISCONNECTED
        self._metrics.record_fix_session("DISCONNECTED")
        return True

    async def reconnect(self) -> bool:
        """Reconnect to the broker.

        Returns:
            True if reconnected successfully
        """
        self.status = GatewayStatus.RECONNECTING
        logger.info("Reconnecting to broker %s", self.name)

        await self.disconnect()
        return await self.connect(**self._credentials)

    # ── Order Management ───────────────────────────────────────────

    async def submit_order(
        self,
        order_id: str = "",
        symbol: str = "",
        side: str = "BUY",
        quantity: float = 0.0,
        order_type: str = "LIMIT",
        limit_price: float = 0.0,
        venue: str = "",
        broker: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """Submit an order through the broker.

        Args:
            order_id: Client order identifier
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            order_type: LIMIT, MARKET, etc.
            limit_price: Limit price
            venue: Execution venue
            broker: Broker identifier
            **kwargs: Additional order parameters

        Returns:
            Order submission response
        """
        if self.status != GatewayStatus.CONNECTED:
            return {"status": "ERROR", "message": f"Gateway not connected (status={self.status.value})"}

        request = {
            "order_id": order_id or str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "limit_price": limit_price,
            "venue": venue,
            "broker": broker or self.name,
            "session_id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }

        try:
            if self.adapter:
                result = await self.adapter.submit(request)
            else:
                result = self._mock_submit(request)

            self._metrics.record_order_submitted(self.name)
            return result
        except Exception as e:
            logger.error("Order submission failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    async def cancel_order(self, order_id: str, broker_order_id: str = "") -> dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Client order identifier
            broker_order_id: Broker order identifier

        Returns:
            Cancellation response
        """
        if self.status != GatewayStatus.CONNECTED:
            return {"status": "ERROR", "message": "Gateway not connected"}

        try:
            if self.adapter:
                result = await self.adapter.cancel(order_id, broker_order_id)
            else:
                result = {"status": "CANCELLED", "order_id": order_id}

            return result
        except Exception as e:
            logger.error("Order cancellation failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    async def replace_order(
        self,
        order_id: str,
        new_quantity: float = 0.0,
        new_price: float = 0.0,
    ) -> dict[str, Any]:
        """Replace/modify an existing order.

        Args:
            order_id: Client order identifier
            new_quantity: New quantity
            new_price: New limit price

        Returns:
            Replace response
        """
        if self.status != GatewayStatus.CONNECTED:
            return {"status": "ERROR", "message": "Gateway not connected"}

        try:
            if self.adapter:
                result = await self.adapter.replace(order_id, new_quantity, new_price)
            else:
                result = {"status": "REPLACED", "order_id": order_id}

            return result
        except Exception as e:
            logger.error("Order replace failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    # ── Query ──────────────────────────────────────────────────────

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Query order status from broker.

        Args:
            order_id: Client order identifier

        Returns:
            Order status response
        """
        if self.status != GatewayStatus.CONNECTED:
            return {"status": "ERROR", "message": "Gateway not connected"}

        try:
            if self.adapter:
                return await self.adapter.query_status(order_id)
            return {"status": "UNKNOWN", "order_id": order_id}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    async def get_positions(self) -> list[dict[str, Any]]:
        """Query current positions from broker.

        Returns:
            List of position dictionaries
        """
        if self.status != GatewayStatus.CONNECTED:
            return []

        try:
            if self.adapter:
                return await self.adapter.query_positions()
            return []
        except Exception as e:
            logger.error("Position query failed: %s", e)
            return []

    # ── Internal ───────────────────────────────────────────────────

    def _mock_submit(self, request: dict[str, Any]) -> dict[str, Any]:
        """Mock order submission for development.

        Args:
            request: Order request

        Returns:
            Mock response
        """
        return {
            "status": "SUBMITTED",
            "order_id": request["order_id"],
            "broker_order_id": f"BRK_{uuid.uuid4().hex[:8]}",
            "broker": self.name,
            "session_id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @property
    def is_connected(self) -> bool:
        """Whether the gateway is connected."""
        return self.status == GatewayStatus.CONNECTED

    def to_dict(self) -> dict[str, Any]:
        """Serialize gateway state."""
        return {
            "name": self.name,
            "status": self.status.value,
            "session_id": self.session_id,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "is_connected": self.is_connected,
        }

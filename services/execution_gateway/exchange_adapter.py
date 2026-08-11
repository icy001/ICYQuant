"""Exchange Adapter — Exchange-specific protocol adapter.

Handles exchange-level communication including order book access,
trade reporting, and market data. Abstracts exchange-specific
message formats and protocols.

Exchange Hierarchy::

    BrokerGateway → ExchangeAdapter → Exchange Protocol → Exchange

Usage::

    adapter = ExchangeAdapter("NYSE", protocol="FIX")
    await adapter.connect(session_config)
    await adapter.send_order(order_request)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExchangeProtocol(str, Enum):
    """Exchange communication protocol."""

    FIX = "FIX"
    OUCH = "OUCH"
    BINARY = "BINARY"
    REST = "REST"
    WS = "WEBSOCKET"
    GRPC = "GRPC"


class ExchangeAdapter:
    """Exchange-level protocol adapter.

    Handles direct exchange communication, translating internal
    order representations to exchange-specific message formats.

    Attributes:
        exchange_name: Exchange identifier
        protocol: Communication protocol
        _is_connected: Connection state
        _session_id: Current session identifier
        _connected_at: Connection timestamp
        _supported_products: Supported product types
    """

    def __init__(
        self,
        exchange_name: str,
        protocol: ExchangeProtocol = ExchangeProtocol.FIX,
    ) -> None:
        self.exchange_name = exchange_name
        self.protocol = protocol
        self._is_connected = False
        self._session_id: str = ""
        self._connected_at: Optional[datetime] = None
        self._supported_products: list[str] = ["EQUITY", "ETF"]

    # ── Connection ─────────────────────────────────────────────────

    async def connect(self, config: Optional[dict[str, Any]] = None) -> bool:
        """Connect to the exchange.

        Args:
            config: Connection configuration

        Returns:
            True if connected
        """
        logger.info(
            "Connecting to exchange %s via %s",
            self.exchange_name,
            self.protocol.value,
        )

        try:
            self._is_connected = True
            self._connected_at = datetime.now(timezone.utc)
            self._session_id = f"EX_{self.exchange_name}_{int(self._connected_at.timestamp())}"

            logger.info(
                "Connected to exchange %s (session=%s)",
                self.exchange_name,
                self._session_id,
            )
            return True
        except Exception as e:
            logger.error("Exchange connection failed: %s", e)
            return False

    async def disconnect(self) -> bool:
        """Disconnect from the exchange.

        Returns:
            True if disconnected
        """
        self._is_connected = False
        logger.info("Disconnected from exchange %s", self.exchange_name)
        return True

    # ── Order Operations ───────────────────────────────────────────

    async def send_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Send an order to the exchange.

        Args:
            order: Order parameters

        Returns:
            Exchange response
        """
        if not self._is_connected:
            return {"status": "ERROR", "message": "Not connected to exchange"}

        formatted = self._format_order(order)
        response = await self._transmit(formatted)
        return self._parse_response(response)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an order on the exchange.

        Args:
            order_id: Exchange order identifier

        Returns:
            Cancellation response
        """
        if not self._is_connected:
            return {"status": "ERROR", "message": "Not connected to exchange"}
        return {"status": "CANCELLED", "order_id": order_id}

    async def modify_order(
        self,
        order_id: str,
        new_price: float = 0.0,
        new_quantity: float = 0.0,
    ) -> dict[str, Any]:
        """Modify an order on the exchange.

        Args:
            order_id: Exchange order identifier
            new_price: New limit price
            new_quantity: New quantity

        Returns:
            Modify response
        """
        if not self._is_connected:
            return {"status": "ERROR", "message": "Not connected to exchange"}
        return {"status": "MODIFIED", "order_id": order_id}

    # ── Market Data ────────────────────────────────────────────────

    async def get_order_book(self, symbol: str, depth: int = 10) -> dict[str, Any]:
        """Get order book snapshot.

        Args:
            symbol: Trading symbol
            depth: Book depth levels

        Returns:
            Order book dictionary
        """
        return {
            "symbol": symbol,
            "depth": depth,
            "bids": [],
            "asks": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_last_trade(self, symbol: str) -> Optional[dict[str, Any]]:
        """Get last trade price.

        Args:
            symbol: Trading symbol

        Returns:
            Last trade dictionary
        """
        return {"symbol": symbol, "price": 0.0, "quantity": 0}

    # ── Internal ───────────────────────────────────────────────────

    def _format_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Format an order for exchange protocol.

        Args:
            order: Internal order representation

        Returns:
            Exchange-formatted order
        """
        return {
            "exchange": self.exchange_name,
            "symbol": order.get("symbol", ""),
            "side": order.get("side", "BUY"),
            "quantity": order.get("quantity", 0),
            "order_type": order.get("order_type", "LIMIT"),
            "price": order.get("limit_price", 0.0),
            "session_id": self._session_id,
        }

    async def _transmit(self, message: dict[str, Any]) -> dict[str, Any]:
        """Transmit a message to the exchange.

        Args:
            message: Formatted message

        Returns:
            Exchange response
        """
        # In production: serialize and send via the configured protocol
        return {"status": "ACK", "message": message}

    def _parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse an exchange response.

        Args:
            response: Raw exchange response

        Returns:
            Standardized response
        """
        return {
            "status": response.get("status", "UNKNOWN"),
            "exchange": self.exchange_name,
            "session_id": self._session_id,
            "message": response.get("message", ""),
        }

    # ── Properties ─────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def supports_product(self, product: str) -> bool:
        """Check if exchange supports a product type.

        Args:
            product: Product type

        Returns:
            True if supported
        """
        return product.upper() in [p.upper() for p in self._supported_products]

    def to_dict(self) -> dict[str, Any]:
        """Serialize adapter state."""
        return {
            "exchange_name": self.exchange_name,
            "protocol": self.protocol.value,
            "is_connected": self._is_connected,
            "session_id": self._session_id,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "supported_products": self._supported_products,
        }

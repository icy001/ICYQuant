"""Broker Adapter — Protocol adapter for broker-specific communication.

Abstracts broker-specific API differences behind a uniform interface.
Each broker implementation extends this adapter to handle protocol
translation, message formatting, and response parsing.

Adapter Pattern::

    EMS → BrokerAdapter.submit() → format → send → parse → response

Usage::

    class MyBrokerAdapter(BrokerAdapter):
        async def submit(self, request):
            formatted = self.format(request)
            raw = await self.send(formatted)
            return self.parse(raw)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """Abstract broker adapter base class.

    Defines the interface for broker-specific protocol adapters.
    Each concrete adapter handles a specific broker's API.

    Attributes:
        broker_name: Broker identifier
        _supported_order_types: Order types supported by this broker
        _supported_venues: Venues accessible through this broker
    """

    def __init__(self, broker_name: str) -> None:
        self.broker_name = broker_name
        self._supported_order_types: list[str] = ["LIMIT", "MARKET"]
        self._supported_venues: list[str] = []

    # ── Order Operations ───────────────────────────────────────────

    @abstractmethod
    async def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        """Submit an order to the broker.

        Args:
            request: Order request dictionary

        Returns:
            Order response dictionary
        """
        ...

    @abstractmethod
    async def cancel(self, order_id: str, broker_order_id: str = "") -> dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Client order identifier
            broker_order_id: Broker order identifier

        Returns:
            Cancellation response
        """
        ...

    async def replace(
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
        return {"status": "ERROR", "message": "Replace not supported by this broker"}

    async def query_status(self, order_id: str) -> dict[str, Any]:
        """Query order status.

        Args:
            order_id: Client order identifier

        Returns:
            Order status response
        """
        return {"status": "UNKNOWN", "order_id": order_id}

    async def query_positions(self) -> list[dict[str, Any]]:
        """Query current positions.

        Returns:
            List of position dictionaries
        """
        return []

    # ── Message Formatting ─────────────────────────────────────────

    def format(self, request: dict[str, Any]) -> dict[str, Any]:
        """Format a request for this broker's protocol.

        Args:
            request: Generic order request

        Returns:
            Broker-specific formatted request
        """
        return {
            "broker": self.broker_name,
            "order_id": request.get("order_id", ""),
            "symbol": request.get("symbol", ""),
            "side": request.get("side", "BUY"),
            "quantity": request.get("quantity", 0),
            "order_type": request.get("order_type", "LIMIT"),
            "limit_price": request.get("limit_price", 0.0),
        }

    def parse(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse a broker response to standard format.

        Args:
            response: Broker-specific response

        Returns:
            Standardized response
        """
        return {
            "status": response.get("status", "UNKNOWN"),
            "order_id": response.get("order_id", ""),
            "broker_order_id": response.get("broker_order_id", ""),
            "message": response.get("message", ""),
        }

    # ── Validation ─────────────────────────────────────────────────

    def validate(self, request: dict[str, Any]) -> tuple[bool, str]:
        """Validate an order request for this broker.

        Args:
            request: Order request to validate

        Returns:
            (is_valid, error_message)
        """
        order_type = request.get("order_type", "LIMIT")
        if order_type not in self._supported_order_types:
            return False, f"Order type {order_type} not supported by {self.broker_name}"

        quantity = request.get("quantity", 0)
        if quantity <= 0:
            return False, "Quantity must be positive"

        symbol = request.get("symbol", "")
        if not symbol:
            return False, "Symbol is required"

        return True, ""

    # ── Capabilities ───────────────────────────────────────────────

    def supports_order_type(self, order_type: str) -> bool:
        """Check if this broker supports an order type.

        Args:
            order_type: Order type string

        Returns:
            True if supported
        """
        return order_type in self._supported_order_types

    def supports_venue(self, venue: str) -> bool:
        """Check if this broker supports a venue.

        Args:
            venue: Venue name

        Returns:
            True if supported
        """
        if not self._supported_venues:
            return True  # All if none specified
        return venue in self._supported_venues

    def get_capabilities(self) -> dict[str, Any]:
        """Get broker capabilities.

        Returns:
            Capabilities dictionary
        """
        return {
            "broker_name": self.broker_name,
            "supported_order_types": self._supported_order_types,
            "supported_venues": self._supported_venues,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize adapter state."""
        return self.get_capabilities()

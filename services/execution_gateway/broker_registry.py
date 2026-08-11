"""Broker Registry — Broker registration and lifecycle management.

Manages registered brokers, their gateways, adapters, and sessions.
Provides broker lookup and status monitoring.

Registration::

    registry = BrokerRegistry()
    registry.register("PRIMARY", gateway)
    broker = registry.get("PRIMARY")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from services.execution_gateway.broker_gateway import BrokerGateway

logger = logging.getLogger(__name__)


class BrokerRegistry:
    """Broker registration and management registry.

    Stores and manages all registered broker gateways and their
    connection state.

    Attributes:
        _brokers: Broker name → BrokerGateway mapping
        _default_broker: Default broker name for routing
    """

    def __init__(self) -> None:
        self._brokers: dict[str, BrokerGateway] = {}
        self._default_broker: str = ""

    # ── Registration ───────────────────────────────────────────────

    def register(self, name: str, gateway: BrokerGateway) -> bool:
        """Register a broker gateway.

        Args:
            name: Broker identifier
            gateway: Broker gateway instance

        Returns:
            True if registered
        """
        if name in self._brokers:
            logger.warning("Broker %s already registered, replacing", name)

        self._brokers[name] = gateway
        if not self._default_broker:
            self._default_broker = name

        logger.info("Broker registered: %s", name)
        return True

    def unregister(self, name: str) -> bool:
        """Unregister a broker.

        Args:
            name: Broker identifier

        Returns:
            True if unregistered
        """
        if name in self._brokers:
            del self._brokers[name]
            if self._default_broker == name:
                self._default_broker = next(iter(self._brokers), "")
            logger.info("Broker unregistered: %s", name)
            return True
        return False

    # ── Connection ─────────────────────────────────────────────────

    async def connect(self, name: str, **credentials) -> bool:
        """Connect to a registered broker.

        Args:
            name: Broker identifier
            **credentials: Authentication credentials

        Returns:
            True if connected
        """
        broker = self._brokers.get(name)
        if not broker:
            logger.error("Broker %s not registered", name)
            return False

        return await broker.connect(**credentials)

    async def disconnect(self, name: str) -> bool:
        """Disconnect from a broker.

        Args:
            name: Broker identifier

        Returns:
            True if disconnected
        """
        broker = self._brokers.get(name)
        if not broker:
            return False
        return await broker.disconnect()

    async def connect_all(self, credentials_map: dict[str, dict[str, Any]]) -> dict[str, bool]:
        """Connect to all registered brokers.

        Args:
            credentials_map: Broker name → credentials mapping

        Returns:
            Dict of broker name → success
        """
        results = {}
        for name in self._brokers:
            creds = credentials_map.get(name, {})
            results[name] = await self.connect(name, **creds)
        return results

    # ── Query ──────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[BrokerGateway]:
        """Get a registered broker gateway.

        Args:
            name: Broker identifier

        Returns:
            BrokerGateway or None
        """
        return self._brokers.get(name)

    def get_default(self) -> Optional[BrokerGateway]:
        """Get the default broker gateway.

        Returns:
            Default BrokerGateway or None
        """
        return self._brokers.get(self._default_broker)

    def get_connected(self) -> list[BrokerGateway]:
        """Get all connected broker gateways.

        Returns:
            List of connected BrokerGateway instances
        """
        return [b for b in self._brokers.values() if b.is_connected]

    def get_all(self) -> list[BrokerGateway]:
        """Get all registered broker gateways.

        Returns:
            List of all BrokerGateway instances
        """
        return list(self._brokers.values())

    def set_default(self, name: str) -> bool:
        """Set the default broker.

        Args:
            name: Broker identifier

        Returns:
            True if set successfully
        """
        if name in self._brokers:
            self._default_broker = name
            logger.info("Default broker set to %s", name)
            return True
        return False

    # ── Properties ─────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Number of registered brokers."""
        return len(self._brokers)

    @property
    def connected_count(self) -> int:
        """Number of connected brokers."""
        return len(self.get_connected())

    @property
    def broker_names(self) -> list[str]:
        """List of registered broker names."""
        return list(self._brokers.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "count": self.count,
            "connected_count": self.connected_count,
            "default_broker": self._default_broker,
            "brokers": {n: b.to_dict() for n, b in self._brokers.items()},
        }

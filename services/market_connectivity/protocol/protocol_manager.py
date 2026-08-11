"""
Protocol Manager — Central manager for all protocol implementations.

Registers, resolves, and manages protocol instances with a unified
interface for connect, send, receive, and close operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Protocol:
    """Base protocol interface that all protocols must implement."""

    async def connect(self, endpoint: str, **kwargs: Any) -> bool:
        raise NotImplementedError

    async def send(self, data: Any) -> bool:
        raise NotImplementedError

    async def receive(self) -> Optional[Any]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        raise NotImplementedError

    @property
    def protocol_name(self) -> str:
        raise NotImplementedError


class ProtocolManager:
    """
    Central protocol registry and manager.

    Registers all supported protocols, creates protocol instances
    via factory, and manages the protocol lifecycle.

    Usage::

        manager = ProtocolManager()
        await manager.initialize()
        ws = await manager.create("websocket")
        await ws.connect("wss://example.com/ws")
        await ws.send({"method": "subscribe"})
        data = await ws.receive()
        await ws.close()
    """

    def __init__(self) -> None:
        self._protocols: dict[str, type[Protocol]] = {}
        self._instances: dict[str, Protocol] = {}

    async def initialize(self) -> None:
        """Initialize the protocol manager."""
        logger.info("ProtocolManager initialized.")

    # ---- Registration ----

    def register(self, name: str, protocol_cls: type[Protocol]) -> None:
        """Register a protocol implementation."""
        self._protocols[name] = protocol_cls
        logger.info("Protocol registered: %s", name)

    def unregister(self, name: str) -> bool:
        """Unregister a protocol."""
        if name in self._protocols:
            del self._protocols[name]
            return True
        return False

    def get_protocol(self, name: str) -> Optional[type[Protocol]]:
        """Get a registered protocol class."""
        return self._protocols.get(name)

    def list_protocols(self) -> list[str]:
        """List all registered protocol names."""
        return list(self._protocols.keys())

    # ---- Instance Management ----

    async def create(
        self, protocol_name: str, instance_id: Optional[str] = None, **kwargs: Any
    ) -> Optional[Protocol]:
        """Create a new protocol instance."""
        protocol_cls = self._protocols.get(protocol_name)
        if protocol_cls is None:
            logger.error("Unknown protocol: %s", protocol_name)
            return None

        instance = protocol_cls(**kwargs)
        mid = instance_id or f"{protocol_name}_{id(instance)}"
        self._instances[mid] = instance
        logger.debug("Created protocol instance: %s (%s)", protocol_name, mid)
        return instance

    async def get_instance(self, instance_id: str) -> Optional[Protocol]:
        """Get an active protocol instance."""
        return self._instances.get(instance_id)

    async def remove_instance(self, instance_id: str) -> bool:
        """Remove and close a protocol instance."""
        instance = self._instances.pop(instance_id, None)
        if instance:
            try:
                await instance.close()
            except Exception:
                logger.exception("Error closing protocol instance: %s", instance_id)
            return True
        return False

    async def get_instance_count(self) -> dict[str, int]:
        """Get the count of active instances per protocol type."""
        counts: dict[str, int] = {}
        for instance in self._instances.values():
            name = instance.protocol_name
            counts[name] = counts.get(name, 0) + 1
        return counts

    async def close_all(self) -> None:
        """Close all protocol instances."""
        for instance_id in list(self._instances.keys()):
            await self.remove_instance(instance_id)
        logger.info("All protocol instances closed.")

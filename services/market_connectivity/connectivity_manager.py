"""
Connectivity Manager — Orchestrates the lifecycle of all exchange
connections including connect/disconnect/reconnect/discover operations
across the connectivity registry.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .connectivity_registry import ConnectivityRegistry, RegistryEntryStatus

logger = logging.getLogger(__name__)


class ConnectivityManager:
    """
    Central manager for all exchange connectivity operations.

    Coordinates connection lifecycle, session management, and
    health monitoring across all registered exchanges.

    Usage::

        registry = ConnectivityRegistry()
        manager = ConnectivityManager(registry)
        await manager.initialize()
        await manager.connect("binance")
        await manager.disconnect("binance")
    """

    def __init__(self, registry: ConnectivityRegistry) -> None:
        self._registry = registry
        self._exchange_managers: dict[str, Any] = {}
        self._connection_managers: dict[str, Any] = {}
        self._session_pools: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connectivity manager."""
        logger.info("ConnectivityManager initialized.")

    # ---- Exchange Lifecycle ----

    async def register_exchange(
        self, exchange_id: str, capabilities: dict[str, Any], **kwargs: Any
    ) -> bool:
        """Register a new exchange with capabilities."""
        async with self._lock:
            try:
                await self._registry.register_exchange(
                    exchange_id=exchange_id,
                    capabilities=capabilities,
                    **kwargs,
                )
                logger.info("Exchange registered: %s", exchange_id)
                return True
            except Exception:
                logger.exception("Failed to register exchange: %s", exchange_id)
                return False

    async def unregister_exchange(self, exchange_id: str) -> bool:
        """Unregister an exchange and close its connections."""
        async with self._lock:
            await self.disconnect(exchange_id)
            await self._registry.unregister_exchange(exchange_id)
            logger.info("Exchange unregistered: %s", exchange_id)
            return True

    async def connect(self, exchange_id: str, **kwargs: Any) -> bool:
        """Establish connection to an exchange."""
        entry = await self._registry.get_entry(exchange_id)
        if entry is None:
            logger.error("Exchange not registered: %s", exchange_id)
            return False

        if entry.status == RegistryEntryStatus.CONNECTED:
            logger.info("Exchange already connected: %s", exchange_id)
            return True

        try:
            await self._registry.update_status(exchange_id, RegistryEntryStatus.CONNECTING)
            # Delegate to the exchange manager for actual connection
            logger.info("Connecting to exchange: %s", exchange_id)
            await asyncio.sleep(0.01)  # placeholder for actual connection logic
            await self._registry.update_status(exchange_id, RegistryEntryStatus.CONNECTED)
            logger.info("Connected to exchange: %s", exchange_id)
            return True
        except Exception:
            logger.exception("Failed to connect to exchange: %s", exchange_id)
            await self._registry.update_status(exchange_id, RegistryEntryStatus.ERROR)
            return False

    async def disconnect(self, exchange_id: str) -> bool:
        """Disconnect from an exchange."""
        entry = await self._registry.get_entry(exchange_id)
        if entry is None:
            logger.warning("Exchange not found: %s", exchange_id)
            return False

        if entry.status == RegistryEntryStatus.DISCONNECTED:
            return True

        try:
            await self._registry.update_status(exchange_id, RegistryEntryStatus.DISCONNECTING)
            logger.info("Disconnecting from exchange: %s", exchange_id)
            await asyncio.sleep(0.01)  # placeholder for actual disconnection logic
            await self._registry.update_status(exchange_id, RegistryEntryStatus.DISCONNECTED)
            logger.info("Disconnected from exchange: %s", exchange_id)
            return True
        except Exception:
            logger.exception("Failed to disconnect from exchange: %s", exchange_id)
            await self._registry.update_status(exchange_id, RegistryEntryStatus.ERROR)
            return False

    async def reconnect(self, exchange_id: str, **kwargs: Any) -> bool:
        """Reconnect to an exchange."""
        await self.disconnect(exchange_id)
        await asyncio.sleep(0.5)  # brief cooldown
        return await self.connect(exchange_id, **kwargs)

    async def discover(self) -> list[dict[str, Any]]:
        """Discover available exchanges and their endpoints."""
        entries = await self._registry.list_entries()
        results = []
        for entry in entries:
            results.append({
                "exchange_id": entry.exchange_id,
                "status": entry.status.value,
                "capabilities": entry.capabilities,
                "endpoints": entry.endpoints,
                "connected_at": entry.connected_at.isoformat() if entry.connected_at else None,
            })
        return results

    async def get_active_exchanges(self) -> list[str]:
        """Get list of currently connected exchange IDs."""
        entries = await self._registry.list_entries()
        return [
            e.exchange_id
            for e in entries
            if e.status == RegistryEntryStatus.CONNECTED
        ]

    async def get_exchange_info(self, exchange_id: str) -> Optional[dict[str, Any]]:
        """Get detailed info about a specific exchange."""
        entry = await self._registry.get_entry(exchange_id)
        if entry is None:
            return None
        return {
            "exchange_id": entry.exchange_id,
            "status": entry.status.value,
            "capabilities": entry.capabilities,
            "endpoints": entry.endpoints,
            "metadata": entry.metadata,
            "connected_at": entry.connected_at.isoformat() if entry.connected_at else None,
        }

    async def shutdown(self) -> None:
        """Gracefully disconnect all exchanges."""
        active = await self.get_active_exchanges()
        tasks = [self.disconnect(eid) for eid in active]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("ConnectivityManager shut down.")

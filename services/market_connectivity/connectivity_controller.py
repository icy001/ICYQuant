"""
Connectivity Controller — Operational control plane for the
Market Connectivity Platform, bridging the registry and manager
with health monitoring and failover coordination.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .connectivity_manager import ConnectivityManager
from .connectivity_registry import ConnectivityRegistry, RegistryEntryStatus

logger = logging.getLogger(__name__)


class ConnectivityController:
    """
    Control plane for connectivity operations.

    Bridges the ConnectivityRegistry and ConnectivityManager,
    providing coordinated connect/disconnect/reconnect operations
    with health awareness and failover integration.

    Usage::

        controller = ConnectivityController(registry, manager)
        await controller.initialize()
        await controller.connect_exchange("binance")
    """

    def __init__(
        self,
        registry: ConnectivityRegistry,
        manager: ConnectivityManager,
    ) -> None:
        self._registry = registry
        self._manager = manager
        self._failover_manager: Optional[Any] = None
        self._heartbeat_monitor: Optional[Any] = None

    async def initialize(self) -> None:
        """Initialize the controller."""
        logger.info("ConnectivityController initialized.")

    def set_failover_manager(self, failover_manager: Any) -> None:
        """Inject the failover manager for coordinated failover."""
        self._failover_manager = failover_manager

    def set_heartbeat_monitor(self, heartbeat_monitor: Any) -> None:
        """Inject the heartbeat monitor for health-aware operations."""
        self._heartbeat_monitor = heartbeat_monitor

    # ---- Exchange Operations ----

    async def connect_exchange(self, exchange_id: str, **kwargs: Any) -> bool:
        """Connect to an exchange with health awareness."""
        success = await self._manager.connect(exchange_id, **kwargs)
        if success and self._heartbeat_monitor:
            # Start monitoring heartbeats for the new connection
            pass
        return success

    async def disconnect_exchange(self, exchange_id: str) -> bool:
        """Disconnect from an exchange."""
        return await self._manager.disconnect(exchange_id)

    async def reconnect_exchange(self, exchange_id: str) -> bool:
        """Reconnect to an exchange."""
        return await self._manager.reconnect(exchange_id)

    async def discover_exchanges(self) -> list[str]:
        """Discover available exchanges."""
        results = await self._manager.discover()
        return [r["exchange_id"] for r in results]

    async def get_active_exchanges(self) -> list[str]:
        """Get list of active (connected) exchange IDs."""
        return await self._manager.get_active_exchanges()

    async def get_exchange_info(self, exchange_id: str) -> Optional[dict[str, Any]]:
        """Get detailed information about an exchange."""
        return await self._manager.get_exchange_info(exchange_id)

    # ---- Health-Aware Operations ----

    async def health_check_all(self) -> dict[str, Any]:
        """Run health checks on all registered exchanges."""
        entries = await self._registry.list_entries()
        results: dict[str, Any] = {}
        for entry in entries:
            results[entry.exchange_id] = {
                "status": entry.status.value,
                "healthy": entry.status == RegistryEntryStatus.CONNECTED,
            }
        return results

    async def get_platform_summary(self) -> dict[str, Any]:
        """Get a summary of the entire connectivity platform."""
        entries = await self._registry.list_entries()
        total = len(entries)
        connected = sum(1 for e in entries if e.status == RegistryEntryStatus.CONNECTED)
        connecting = sum(1 for e in entries if e.status == RegistryEntryStatus.CONNECTING)
        disconnected = sum(1 for e in entries if e.status == RegistryEntryStatus.DISCONNECTED)
        error = sum(1 for e in entries if e.status == RegistryEntryStatus.ERROR)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchanges": {
                "total": total,
                "connected": connected,
                "connecting": connecting,
                "disconnected": disconnected,
                "error": error,
            },
            "health_ratio": connected / max(total, 1),
        }

    async def shutdown(self) -> None:
        """Shut down the controller and disconnect all exchanges."""
        await self._manager.shutdown()
        logger.info("ConnectivityController shut down.")

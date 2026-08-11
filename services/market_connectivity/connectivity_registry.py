"""
Connectivity Registry — Central registry for all exchange connections
tracking registration status, capabilities, endpoints, and metadata.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RegistryEntryStatus(str, Enum):
    REGISTERED = "registered"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SUSPENDED = "suspended"


@dataclass
class RegistryEntry:
    exchange_id: str
    status: RegistryEntryStatus = RegistryEntryStatus.REGISTERED
    capabilities: dict[str, Any] = field(default_factory=dict)
    endpoints: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    error_message: str = ""
    retry_count: int = 0


class ConnectivityRegistry:
    """
    Central registry for managing exchange connectivity entries.

    Tracks registration, connection status, capabilities, endpoints,
    and metadata for all exchanges connected to the platform.

    Usage::

        registry = ConnectivityRegistry()
        await registry.initialize()
        await registry.register_exchange("binance", capabilities={...})
        entry = await registry.get_entry("binance")
    """

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the registry."""
        logger.info("ConnectivityRegistry initialized.")

    # ---- CRUD Operations ----

    async def register_exchange(
        self,
        exchange_id: str,
        capabilities: Optional[dict[str, Any]] = None,
        endpoints: Optional[list[dict[str, Any]]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RegistryEntry:
        """Register a new exchange or update an existing registration."""
        async with self._lock:
            if exchange_id in self._entries:
                entry = self._entries[exchange_id]
                if capabilities:
                    entry.capabilities.update(capabilities)
                if endpoints:
                    entry.endpoints = endpoints
                if metadata:
                    entry.metadata.update(metadata)
                entry.status = RegistryEntryStatus.REGISTERED
                logger.info("Exchange updated: %s", exchange_id)
                return entry

            entry = RegistryEntry(
                exchange_id=exchange_id,
                capabilities=capabilities or {},
                endpoints=endpoints or [],
                metadata=metadata or {},
            )
            self._entries[exchange_id] = entry
            logger.info("Exchange registered: %s", exchange_id)
            return entry

    async def unregister_exchange(self, exchange_id: str) -> bool:
        """Remove an exchange from the registry."""
        async with self._lock:
            if exchange_id in self._entries:
                del self._entries[exchange_id]
                logger.info("Exchange unregistered: %s", exchange_id)
                return True
            return False

    async def get_entry(self, exchange_id: str) -> Optional[RegistryEntry]:
        """Get a registry entry by exchange ID."""
        return self._entries.get(exchange_id)

    async def list_entries(self) -> list[RegistryEntry]:
        """List all registered exchange entries."""
        return list(self._entries.values())

    async def update_status(
        self, exchange_id: str, status: RegistryEntryStatus, error_message: str = ""
    ) -> bool:
        """Update the connection status of an exchange."""
        async with self._lock:
            entry = self._entries.get(exchange_id)
            if entry is None:
                logger.warning("Cannot update status: exchange not found: %s", exchange_id)
                return False

            entry.status = status
            if status == RegistryEntryStatus.CONNECTED:
                entry.connected_at = datetime.now(timezone.utc)
                entry.retry_count = 0
                entry.error_message = ""
            elif status == RegistryEntryStatus.ERROR:
                entry.error_message = error_message
                entry.retry_count += 1
            elif status == RegistryEntryStatus.DISCONNECTED:
                entry.connected_at = None

            return True

    async def update_heartbeat(self, exchange_id: str) -> bool:
        """Update the last heartbeat timestamp for an exchange."""
        entry = self._entries.get(exchange_id)
        if entry is None:
            return False
        entry.last_heartbeat = datetime.now(timezone.utc)
        return True

    async def update_endpoints(
        self, exchange_id: str, endpoints: list[dict[str, Any]]
    ) -> bool:
        """Update the endpoint list for an exchange."""
        entry = self._entries.get(exchange_id)
        if entry is None:
            return False
        entry.endpoints = endpoints
        return True

    async def get_summary(self) -> dict[str, Any]:
        """Get a summary of all registry entries."""
        entries = list(self._entries.values())
        status_counts: dict[str, int] = {}
        for entry in entries:
            s = entry.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total_exchanges": len(entries),
            "status_counts": status_counts,
            "exchanges": [
                {
                    "exchange_id": e.exchange_id,
                    "status": e.status.value,
                    "connected_at": e.connected_at.isoformat() if e.connected_at else None,
                    "retry_count": e.retry_count,
                }
                for e in entries
            ],
        }

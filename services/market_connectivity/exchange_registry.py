"""
Exchange Registry — Registry for managing exchange definitions,
their capabilities, supported protocols, endpoints, and operational status.

Supports dynamic registration of new exchanges with full metadata.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExchangeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    TESTING = "testing"


@dataclass
class ExchangeEntry:
    exchange_id: str
    name: str
    status: ExchangeStatus = ExchangeStatus.ACTIVE
    capabilities: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)
    endpoints: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    regions: list[str] = field(default_factory=list)
    asset_classes: list[str] = field(default_factory=list)
    fee_tier: str = "standard"
    rate_limits: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExchangeRegistry:
    """
    Registry for all exchange definitions in the platform.

    Maintains the canonical list of exchanges with their
    capabilities, protocols, endpoints, and status.

    Exchange → Capabilities → Protocols → Endpoints → Status

    Usage::

        registry = ExchangeRegistry()
        await registry.initialize()
        await registry.register(ExchangeEntry("binance", "Binance", ...))
        exchanges = await registry.list_active()
    """

    def __init__(self) -> None:
        self._exchanges: dict[str, ExchangeEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the exchange registry."""
        logger.info("ExchangeRegistry initialized.")

    # ---- CRUD Operations ----

    async def register(self, entry: ExchangeEntry) -> ExchangeEntry:
        """Register a new exchange or update an existing one."""
        async with self._lock:
            existing = self._exchanges.get(entry.exchange_id)
            if existing:
                # Update fields while preserving original registration time
                existing.name = entry.name or existing.name
                existing.status = entry.status
                existing.capabilities = entry.capabilities or existing.capabilities
                existing.protocols = entry.protocols or existing.protocols
                existing.endpoints = entry.endpoints or existing.endpoints
                existing.regions = entry.regions or existing.regions
                existing.asset_classes = entry.asset_classes or existing.asset_classes
                existing.metadata.update(entry.metadata)
                existing.updated_at = datetime.now(timezone.utc)
                logger.info("Exchange updated: %s", entry.exchange_id)
                return existing

            self._exchanges[entry.exchange_id] = entry
            logger.info("Exchange registered: %s (%s)", entry.exchange_id, entry.name)
            return entry

    async def unregister(self, exchange_id: str) -> bool:
        """Remove an exchange from the registry."""
        async with self._lock:
            if exchange_id in self._exchanges:
                del self._exchanges[exchange_id]
                logger.info("Exchange unregistered: %s", exchange_id)
                return True
            return False

    async def get(self, exchange_id: str) -> Optional[ExchangeEntry]:
        """Get exchange by ID."""
        return self._exchanges.get(exchange_id)

    async def list_all(self) -> list[ExchangeEntry]:
        """List all registered exchanges."""
        return list(self._exchanges.values())

    async def list_active(self) -> list[ExchangeEntry]:
        """List only active exchanges."""
        return [
            e for e in self._exchanges.values()
            if e.status == ExchangeStatus.ACTIVE
        ]

    async def list_by_asset_class(self, asset_class: str) -> list[ExchangeEntry]:
        """List exchanges supporting a specific asset class."""
        return [
            e for e in self._exchanges.values()
            if asset_class in e.asset_classes and e.status == ExchangeStatus.ACTIVE
        ]

    async def list_by_capability(self, capability: str) -> list[ExchangeEntry]:
        """List exchanges supporting a specific capability."""
        return [
            e for e in self._exchanges.values()
            if capability in e.capabilities and e.status == ExchangeStatus.ACTIVE
        ]

    async def list_by_protocol(self, protocol: str) -> list[ExchangeEntry]:
        """List exchanges supporting a specific protocol."""
        return [
            e for e in self._exchanges.values()
            if protocol in e.protocols and e.status == ExchangeStatus.ACTIVE
        ]

    async def update_status(
        self, exchange_id: str, status: ExchangeStatus
    ) -> bool:
        """Update the operational status of an exchange."""
        entry = self._exchanges.get(exchange_id)
        if entry is None:
            return False
        entry.status = status
        entry.updated_at = datetime.now(timezone.utc)
        logger.info("Exchange %s status updated: %s", exchange_id, status.value)
        return True

    async def get_count(self) -> int:
        """Get total number of registered exchanges."""
        return len(self._exchanges)

    async def get_active_count(self) -> int:
        """Get number of active exchanges."""
        return sum(
            1 for e in self._exchanges.values()
            if e.status == ExchangeStatus.ACTIVE
        )

    async def get_summary(self) -> dict[str, Any]:
        """Get registry summary."""
        exchanges = list(self._exchanges.values())
        status_counts: dict[str, int] = {}
        for e in exchanges:
            s = e.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        all_capabilities: set[str] = set()
        all_protocols: set[str] = set()
        for e in exchanges:
            all_capabilities.update(e.capabilities)
            all_protocols.update(e.protocols)

        return {
            "total": len(exchanges),
            "active": sum(1 for e in exchanges if e.status == ExchangeStatus.ACTIVE),
            "status_counts": status_counts,
            "supported_capabilities": sorted(all_capabilities),
            "supported_protocols": sorted(all_protocols),
        }

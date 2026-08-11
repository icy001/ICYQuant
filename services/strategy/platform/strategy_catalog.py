"""
Strategy Catalog — Central strategy inventory and metadata registry.

Maintains the authoritative catalog of all strategies with versioning,
ownership, capabilities, and current status for unified management.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CatalogEntryStatus(str, Enum):
    """Catalog entry lifecycle status."""
    DRAFT = "draft"
    REGISTERED = "registered"
    DEPLOYED = "deployed"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class CatalogEntry:
    """Single strategy catalog entry."""
    strategy_id: str
    name: str
    version: str
    owner: str
    description: str = ""
    status: CatalogEntryStatus = CatalogEntryStatus.DRAFT
    asset_class: str = ""
    strategy_type: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CatalogQuery:
    """Query parameters for catalog searches."""
    name: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[CatalogEntryStatus] = None
    asset_class: Optional[str] = None
    strategy_type: Optional[str] = None
    tags: Optional[list[str]] = None
    search_text: Optional[str] = None


class StrategyCatalog:
    """
    Central strategy catalog for inventory management.

    Provides registration, search, and lifecycle tracking for all
    strategies across the platform.

    Usage::

        catalog = StrategyCatalog()
        await catalog.initialize()
        entry = await catalog.register(CatalogEntry(
            strategy_id="strat_001", name="Momentum Strategy",
            version="1.0.0", owner="quant-team",
        ))
        results = await catalog.search(CatalogQuery(status=CatalogEntryStatus.RUNNING))
    """

    def __init__(self) -> None:
        self._entries: dict[str, CatalogEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the strategy catalog."""
        logger.info("StrategyCatalog initialized.")

    async def stop(self) -> None:
        """Stop the strategy catalog."""
        logger.info("StrategyCatalog stopped.")

    # ---- CRUD Operations ----

    async def register(self, entry: CatalogEntry) -> CatalogEntry:
        """Register a strategy in the catalog."""
        async with self._lock:
            if entry.strategy_id in self._entries:
                raise ValueError(f"Strategy already in catalog: {entry.strategy_id}")
            self._entries[entry.strategy_id] = entry

        logger.info(f"Catalog entry registered: {entry.strategy_id}")
        return entry

    async def update(
        self,
        strategy_id: str,
        **kwargs: Any,
    ) -> Optional[CatalogEntry]:
        """Update a catalog entry."""
        async with self._lock:
            entry = self._entries.get(strategy_id)
            if not entry:
                return None

            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)

            entry.updated_at = datetime.now(timezone.utc)

        logger.info(f"Catalog entry updated: {strategy_id}")
        return entry

    async def update_status(
        self,
        strategy_id: str,
        status: CatalogEntryStatus,
    ) -> Optional[CatalogEntry]:
        """Update a strategy's status."""
        return await self.update(strategy_id, status=status)

    async def get(self, strategy_id: str) -> Optional[CatalogEntry]:
        """Get a catalog entry by ID."""
        return self._entries.get(strategy_id)

    async def delete(self, strategy_id: str) -> bool:
        """Remove a strategy from the catalog."""
        async with self._lock:
            if strategy_id in self._entries:
                del self._entries[strategy_id]
                logger.info(f"Catalog entry deleted: {strategy_id}")
                return True
            return False

    # ---- Search ----

    async def search(self, query: Optional[CatalogQuery] = None) -> list[CatalogEntry]:
        """Search catalog entries with optional filters."""
        results = list(self._entries.values())

        if not query:
            return results

        if query.name:
            results = [e for e in results if query.name.lower() in e.name.lower()]
        if query.owner:
            results = [e for e in results if e.owner == query.owner]
        if query.status:
            results = [e for e in results if e.status == query.status]
        if query.asset_class:
            results = [e for e in results if e.asset_class == query.asset_class]
        if query.strategy_type:
            results = [e for e in results if e.strategy_type == query.strategy_type]
        if query.tags:
            results = [e for e in results if any(t in e.tags for t in query.tags)]
        if query.search_text:
            text = query.search_text.lower()
            results = [
                e for e in results
                if text in e.name.lower()
                or text in e.description.lower()
                or text in e.strategy_id.lower()
            ]

        return results

    async def list_all(self) -> list[CatalogEntry]:
        """List all catalog entries."""
        return list(self._entries.values())

    async def list_by_status(self, status: CatalogEntryStatus) -> list[CatalogEntry]:
        """List entries by status."""
        return [e for e in self._entries.values() if e.status == status]

    async def count(self) -> int:
        """Get total number of catalog entries."""
        return len(self._entries)

    async def count_by_status(self) -> dict[CatalogEntryStatus, int]:
        """Get entry counts by status."""
        counts: dict[CatalogEntryStatus, int] = {}
        for entry in self._entries.values():
            counts[entry.status] = counts.get(entry.status, 0) + 1
        return counts

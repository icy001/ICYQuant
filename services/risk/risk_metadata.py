"""
Risk Metadata — Risk component metadata and versioning.

Provides metadata descriptors for risk policies, profiles, and
components including versioning, ownership, and capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskMetadata:
    """Metadata descriptor for a risk component."""
    component_id: str
    component_type: str  # policy, profile, rule, check
    name: str = ""
    version: str = "1.0.0"
    owner: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskMetadataRegistry:
    """
    Registry for risk component metadata.

    Provides centralized metadata tracking for all risk platform
    components with versioning, ownership, and capability discovery.

    Usage::

        registry = RiskMetadataRegistry()
        await registry.initialize()
        meta = await registry.register(RiskMetadata(
            component_id="check_position_limit",
            component_type="policy",
            name="Position Limit Check",
            owner="risk-team",
        ))
    """

    def __init__(self) -> None:
        self._entries: dict[str, RiskMetadata] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the metadata registry."""
        logger.info("RiskMetadataRegistry initialized.")

    async def stop(self) -> None:
        """Stop the metadata registry."""
        logger.info("RiskMetadataRegistry stopped.")

    # ---- CRUD ----

    async def register(self, entry: RiskMetadata) -> RiskMetadata:
        """Register component metadata."""
        async with self._lock:
            self._entries[entry.component_id] = entry
        logger.info(f"Metadata registered: {entry.component_id} ({entry.component_type})")
        return entry

    async def update(self, component_id: str, **kwargs: Any) -> Optional[RiskMetadata]:
        """Update component metadata."""
        async with self._lock:
            entry = self._entries.get(component_id)
            if not entry:
                return None
            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            entry.updated_at = datetime.now(timezone.utc)
        return entry

    async def remove(self, component_id: str) -> bool:
        """Remove component metadata."""
        async with self._lock:
            if component_id in self._entries:
                del self._entries[component_id]
                return True
            return False

    async def get(self, component_id: str) -> Optional[RiskMetadata]:
        """Get metadata by ID."""
        return self._entries.get(component_id)

    # ---- Query ----

    async def list_by_type(self, component_type: str) -> list[RiskMetadata]:
        """List metadata by component type."""
        return [m for m in self._entries.values() if m.component_type == component_type]

    async def list_by_owner(self, owner: str) -> list[RiskMetadata]:
        """List metadata by owner."""
        return [m for m in self._entries.values() if m.owner == owner]

    async def search(self, query: str) -> list[RiskMetadata]:
        """Search metadata by name, description, or tags."""
        q = query.lower()
        results = []
        for m in self._entries.values():
            if q in m.name.lower() or q in m.description.lower() or any(q in t.lower() for t in m.tags):
                results.append(m)
        return results

    async def list_all(self) -> list[RiskMetadata]:
        """List all metadata entries."""
        return list(self._entries.values())

    async def health_check(self) -> dict[str, Any]:
        """Check metadata registry health."""
        return {
            "status": "healthy",
            "total_entries": len(self._entries),
        }

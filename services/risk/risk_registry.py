"""
Risk Registry — Central registry for risk policies and components.

Manages dynamic registration, versioning, priority ordering,
and hot-reload of risk policies.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RegistryStatus(str, Enum):
    """Registration status."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PolicyEntry:
    """Registry entry for a risk policy."""
    policy_id: str
    name: str
    version: str = "1.0.0"
    category: str = "general"
    priority: int = 0
    status: RegistryStatus = RegistryStatus.ACTIVE
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegistryQuery:
    """Query parameters for registry searches."""
    category: Optional[str] = None
    status: Optional[RegistryStatus] = None
    min_priority: Optional[int] = None
    name_pattern: Optional[str] = None


class RiskRegistry:
    """
    Central registry for risk policies and components.

    Supports dynamic registration, versioning, priority-based
    ordering, and hot-reload of all risk policies.

    Usage::

        registry = RiskRegistry()
        await registry.initialize()
        entry = await registry.register(PolicyEntry(
            policy_id="position_limit",
            name="Position Limit Check",
            priority=10,
        ))
        policies = await registry.list_active(RegistryQuery(category="pre-trade"))
    """

    def __init__(self) -> None:
        self._policies: dict[str, PolicyEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the risk registry."""
        logger.info("RiskRegistry initialized.")

    async def stop(self) -> None:
        """Stop the risk registry."""
        logger.info("RiskRegistry stopped.")

    # ---- Registration ----

    async def register(self, entry: PolicyEntry) -> PolicyEntry:
        """Register a risk policy."""
        async with self._lock:
            if entry.policy_id in self._policies:
                existing = self._policies[entry.policy_id]
                entry.version = self._increment_version(existing.version)
            self._policies[entry.policy_id] = entry

        logger.info(f"Policy registered: {entry.policy_id} v{entry.version}")
        return entry

    async def unregister(self, policy_id: str) -> bool:
        """Remove a policy from the registry."""
        async with self._lock:
            if policy_id in self._policies:
                self._policies[policy_id].status = RegistryStatus.ARCHIVED
                logger.info(f"Policy archived: {policy_id}")
                return True
            return False

    async def update(self, policy_id: str, **kwargs: Any) -> Optional[PolicyEntry]:
        """Update a registered policy."""
        async with self._lock:
            entry = self._policies.get(policy_id)
            if not entry:
                return None
            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            entry.updated_at = datetime.now(timezone.utc)
            entry.version = self._increment_version(entry.version)
        return entry

    async def set_status(self, policy_id: str, status: RegistryStatus) -> Optional[PolicyEntry]:
        """Update a policy's status."""
        return await self.update(policy_id, status=status)

    # ---- Query ----

    async def get(self, policy_id: str) -> Optional[PolicyEntry]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    async def list_active(self, query: Optional[RegistryQuery] = None) -> list[PolicyEntry]:
        """List all active policies, ordered by priority."""
        policies = [p for p in self._policies.values() if p.status == RegistryStatus.ACTIVE]

        if query:
            if query.category:
                policies = [p for p in policies if p.category == query.category]
            if query.status:
                policies = [p for p in policies if p.status == query.status]
            if query.min_priority is not None:
                policies = [p for p in policies if p.priority >= query.min_priority]
            if query.name_pattern:
                pattern = query.name_pattern.lower()
                policies = [p for p in policies if pattern in p.name.lower()]

        return sorted(policies, key=lambda p: p.priority, reverse=True)

    async def list_all(self) -> list[PolicyEntry]:
        """List all registered policies."""
        return list(self._policies.values())

    async def count(self) -> int:
        """Get total registered policies."""
        return len(self._policies)

    async def count_by_category(self) -> dict[str, int]:
        """Get policy counts by category."""
        counts: dict[str, int] = {}
        for entry in self._policies.values():
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts

    # ---- Internal ----

    @staticmethod
    def _increment_version(version: str) -> str:
        """Increment a semantic version."""
        try:
            parts = version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except (ValueError, IndexError):
            return f"{version}.1"

    async def health_check(self) -> dict[str, Any]:
        """Check registry health."""
        return {
            "status": "healthy",
            "total_policies": len(self._policies),
            "active_policies": len([p for p in self._policies.values() if p.status == RegistryStatus.ACTIVE]),
        }

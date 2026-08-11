"""
ICYQuant Unified Data Platform Manager.

Commit 16 Part 1.5 — Central manager for dataset registration, lifecycle,
and cross-subsystem coordination within the unified data platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DatasetStatus(str, Enum):
    """Status of a registered dataset."""
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVING = "archiving"
    ARCHIVED = "archived"
    DELETING = "deleting"
    ERROR = "error"


class DataDomain(str, Enum):
    """Data domain classification."""
    MARKET_DATA = "market_data"
    REFERENCE_DATA = "reference_data"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"
    DERIVED = "derived"
    RESEARCH = "research"
    RISK = "risk"
    EXECUTION = "execution"


@dataclass
class DatasetInfo:
    """Information about a registered dataset."""
    dataset_id: str = ""
    name: str = ""
    domain: DataDomain = DataDomain.MARKET_DATA
    status: DatasetStatus = DatasetStatus.REGISTERED
    owner: str = ""
    description: str = ""
    schema_version: int = 1
    partition_key: str = "date"
    retention_days: int = 365
    quality_score: float = 100.0
    row_count: int = 0
    size_bytes: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DataPlatformManager:
    """Central dataset and platform resource manager.

    Coordinates dataset registration, lifecycle management, and
    cross-subsystem resource allocation across the unified data platform.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, DatasetInfo] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock: Any = None

    async def initialize(self) -> None:
        import asyncio
        self._lock = asyncio.Lock()
        logger.info("DataPlatformManager initialized")

    # ------------------------------------------------------------------
    # Dataset Management
    # ------------------------------------------------------------------

    async def register_dataset(self, info: DatasetInfo) -> str:
        """Register a new dataset."""
        async with self._lock:
            info.created_at = datetime.now(timezone.utc)
            info.updated_at = info.created_at
            self._datasets[info.dataset_id] = info
            logger.info("Dataset registered: %s (%s)", info.dataset_id, info.name)
            return info.dataset_id

    async def get_dataset(self, dataset_id: str) -> Optional[DatasetInfo]:
        """Get dataset info by ID."""
        return self._datasets.get(dataset_id)

    async def list_datasets(
        self, domain: Optional[DataDomain] = None, status: Optional[DatasetStatus] = None,
    ) -> list[DatasetInfo]:
        """List datasets with optional filters."""
        results = list(self._datasets.values())
        if domain:
            results = [d for d in results if d.domain == domain]
        if status:
            results = [d for d in results if d.status == status]
        return results

    async def update_dataset(self, dataset_id: str, **kwargs: Any) -> bool:
        """Update dataset metadata."""
        async with self._lock:
            info = self._datasets.get(dataset_id)
            if not info:
                return False
            for key, value in kwargs.items():
                if hasattr(info, key):
                    setattr(info, key, value)
            info.updated_at = datetime.now(timezone.utc)
            return True

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Mark a dataset for deletion."""
        async with self._lock:
            info = self._datasets.get(dataset_id)
            if not info:
                return False
            info.status = DatasetStatus.DELETING
            info.updated_at = datetime.now(timezone.utc)
            return True

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    async def subscribe(self, dataset_id: str, subscriber_id: str) -> None:
        """Subscribe to a dataset."""
        async with self._lock:
            if dataset_id not in self._subscriptions:
                self._subscriptions[dataset_id] = set()
            self._subscriptions[dataset_id].add(subscriber_id)

    async def unsubscribe(self, dataset_id: str, subscriber_id: str) -> None:
        """Unsubscribe from a dataset."""
        async with self._lock:
            subs = self._subscriptions.get(dataset_id)
            if subs:
                subs.discard(subscriber_id)

    async def get_subscribers(self, dataset_id: str) -> set[str]:
        """Get all subscribers for a dataset."""
        return self._subscriptions.get(dataset_id, set()).copy()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def dataset_count(self) -> int:
        return len(self._datasets)

    def count_by_domain(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ds in self._datasets.values():
            domain = ds.domain.value
            counts[domain] = counts.get(domain, 0) + 1
        return counts

"""
Dataset Registry — centralized registry for all datasets in the data lake
with lifecycle management and access control.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DatasetType(str, Enum):
    TICK = "tick"
    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "orderbook"
    KLINE = "kline"
    OPTION_CHAIN = "option_chain"
    FUTURES = "futures"
    FX = "fx"
    CRYPTO = "crypto"
    INDEX = "index"
    FUNDAMENTAL = "fundamental"
    CORPORATE_ACTION = "corporate_action"
    CUSTOM = "custom"


class DatasetStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PENDING = "pending"


@dataclass
class Dataset:
    name: str
    dataset_type: DatasetType = DatasetType.CUSTOM
    status: DatasetStatus = DatasetStatus.ACTIVE
    description: str = ""
    schema_version: str = "v1"
    partition_strategy: str = "daily"
    retention_days: int = 365
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    owner: str = ""


class DatasetRegistry:
    """
    Centralized registry for all datasets in the data lake.

    Manages dataset lifecycle, metadata, access patterns,
    and provides discovery capabilities.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}

    async def register(self, dataset: Dataset) -> Dataset:
        """Register a new dataset."""
        if dataset.name in self._datasets:
            existing = self._datasets[dataset.name]
            if existing.status != DatasetStatus.DELETED:
                raise ValueError(f"Dataset already exists: {dataset.name}")
        self._datasets[dataset.name] = dataset
        logger.info("Registered dataset: %s (type=%s)", dataset.name, dataset.dataset_type.value)
        return dataset

    async def get_or_create(
        self,
        name: str,
        dataset_type: DatasetType = DatasetType.CUSTOM,
        **kwargs: Any,
    ) -> Dataset:
        """Get an existing dataset or create a new one."""
        if name in self._datasets:
            ds = self._datasets[name]
            if ds.status != DatasetStatus.DELETED:
                return ds
        ds = Dataset(name=name, dataset_type=dataset_type, **kwargs)
        self._datasets[name] = ds
        return ds

    async def get(self, name: str) -> Optional[Dataset]:
        """Get a dataset by name."""
        ds = self._datasets.get(name)
        if ds and ds.status == DatasetStatus.DELETED:
            return None
        return ds

    async def update(self, name: str, **kwargs: Any) -> Optional[Dataset]:
        """Update dataset metadata."""
        ds = self._datasets.get(name)
        if not ds or ds.status == DatasetStatus.DELETED:
            return None
        for key, value in kwargs.items():
            if hasattr(ds, key):
                setattr(ds, key, value)
        ds.updated_at = datetime.now(timezone.utc)
        return ds

    async def delete(self, name: str) -> bool:
        """Soft-delete a dataset."""
        ds = self._datasets.get(name)
        if not ds:
            return False
        ds.status = DatasetStatus.DELETED
        ds.updated_at = datetime.now(timezone.utc)
        logger.info("Deleted dataset: %s", name)
        return True

    async def list_all(self) -> list[dict[str, Any]]:
        """List all active datasets."""
        return [
            {
                "name": ds.name,
                "type": ds.dataset_type.value,
                "status": ds.status.value,
                "retention_days": ds.retention_days,
                "created_at": ds.created_at.isoformat(),
            }
            for ds in self._datasets.values()
            if ds.status != DatasetStatus.DELETED
        ]

    async def list_by_type(self, dataset_type: DatasetType) -> list[Dataset]:
        """List datasets of a specific type."""
        return [
            ds for ds in self._datasets.values()
            if ds.dataset_type == dataset_type and ds.status != DatasetStatus.DELETED
        ]

    async def exists(self, name: str) -> bool:
        """Check if a dataset exists."""
        ds = self._datasets.get(name)
        return ds is not None and ds.status != DatasetStatus.DELETED

    async def archive(self, name: str) -> bool:
        """Archive a dataset."""
        ds = self._datasets.get(name)
        if not ds:
            return False
        ds.status = DatasetStatus.ARCHIVED
        ds.updated_at = datetime.now(timezone.utc)
        return True

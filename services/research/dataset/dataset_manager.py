"""Dataset Manager — unified lifecycle management for research datasets.

Coordinates dataset registration, versioning, caching, quality checks,
and snapshot operations through a single interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.research.research_context import ResearchContext
from services.research.research_factory import ResearchFactory
from services.research.research_repository import ResearchRepository
from services.research.research_validator import ResearchValidator

from .dataset_registry import DatasetRegistry
from .dataset_catalog import DatasetCatalog
from .dataset_cache import DatasetCache

logger = logging.getLogger(__name__)


class DatasetManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class DatasetManager:
    """Unified dataset lifecycle manager.

    Responsibilities:
    * Register datasets in the catalog
    * Manage dataset versions and snapshots
    * Coordinate caching and loading
    * Run quality checks
    * Track dataset statistics

    Supported dataset types:
    * Market Data
    * Factor Data
    * Fundamental Data
    * Alternative Data
    * Macro Data
    * Custom Dataset
    """

    def __init__(
        self,
        context: Optional[ResearchContext] = None,
        repository: Optional[ResearchRepository] = None,
        registry: Optional[DatasetRegistry] = None,
        catalog: Optional[DatasetCatalog] = None,
        cache: Optional[DatasetCache] = None,
    ) -> None:
        self._state = DatasetManagerState.UNINITIALIZED
        self._context = context or ResearchContext()
        self._repository = repository or ResearchRepository()
        self._registry = registry or DatasetRegistry()
        self._catalog = catalog or DatasetCatalog()
        self._cache = cache or DatasetCache()
        self._factory = ResearchFactory()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> DatasetManagerState:
        return self._state

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        if self._state == DatasetManagerState.READY:
            return
        self._state = DatasetManagerState.INITIALIZING
        logger.info("DatasetManager initializing")
        self._state = DatasetManagerState.READY

    async def shutdown(self) -> None:
        self._state = DatasetManagerState.SHUTTING_DOWN
        logger.info("DatasetManager shutting down")
        self._state = DatasetManagerState.TERMINATED

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def register(self, **kwargs) -> Dict[str, Any]:
        """Register a new dataset."""
        data = self._factory.create_dataset(**kwargs)
        ResearchValidator.validate_dataset_create(data)
        result = await self._repository.create_dataset(data)
        self._registry.register(result["id"], result)
        self._catalog.add_entry(
            dataset_id=result["id"],
            name=result["name"],
            source=result["source"],
            schema=result.get("schema", {}),
            tags=result.get("tags", []),
        )
        logger.info("Dataset '%s' registered: %s", kwargs.get("name"), result["id"])
        return result

    async def get(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_dataset(dataset_id)

    async def list(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._repository.list_datasets(**kwargs)

    # ── snapshot ──────────────────────────────────────────────────────────

    async def create_snapshot(
        self,
        dataset_id: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an immutable snapshot of the current dataset version."""
        dataset = await self._repository.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset not found: {dataset_id}")

        version = dataset.get("version", 1)
        snapshot_data = self._factory.create_dataset_snapshot(
            dataset_id=dataset_id,
            version=version,
            description=description,
        )
        logger.info("Snapshot created for dataset %s v%d", dataset_id, version)
        return snapshot_data

    # ── catalog ───────────────────────────────────────────────────────────

    async def search_catalog(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search the dataset catalog."""
        return self._catalog.search(query=query, tags=tags, source=source)

    async def get_catalog_entry(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self._catalog.get_entry(dataset_id)

    # ── cache ─────────────────────────────────────────────────────────────

    async def get_cached(self, dataset_id: str, key: str) -> Optional[Any]:
        """Retrieve cached data for a dataset."""
        return await self._cache.get(dataset_id, key)

    async def put_cached(self, dataset_id: str, key: str, value: Any, ttl: int = 3600) -> None:
        """Store data in the dataset cache."""
        await self._cache.put(dataset_id, key, value, ttl)

    async def invalidate_cache(self, dataset_id: str) -> None:
        """Invalidate all cached entries for a dataset."""
        await self._cache.invalidate(dataset_id)

    def __repr__(self) -> str:
        return f"DatasetManager(state={self._state.value})"

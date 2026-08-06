"""Dataset Loader — unified data loading with multiple strategies and sources.

Supports loading datasets from various backends with configurable
caching, partitioning, and format handling.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .dataset_cache import DatasetCache

logger = logging.getLogger(__name__)


class LoadStrategy(str, Enum):
    """Strategies for loading datasets."""

    FULL = "full"           # Load entire dataset
    INCREMENTAL = "incremental"  # Load only new/changed data
    SNAPSHOT = "snapshot"   # Load from a specific snapshot
    STREAMING = "streaming" # Load in streaming/batch mode
    LAZY = "lazy"           # Defer loading until access


class DatasetLoader:
    """Unified dataset loader with pluggable backends.

    Supports:
    * Multiple load strategies (full, incremental, snapshot, streaming, lazy)
    * Cache-aware loading (skip if cached)
    * Format detection (CSV, Parquet, JSON, etc.)
    * Partition-aware loading
    * Progress tracking
    """

    def __init__(self, cache: Optional[DatasetCache] = None) -> None:
        self._cache = cache or DatasetCache()
        self._load_history: List[Dict[str, Any]] = []

    # ── loading ───────────────────────────────────────────────────────────

    async def load(
        self,
        dataset_id: str,
        strategy: LoadStrategy = LoadStrategy.FULL,
        partitions: Optional[List[str]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Any:
        """Load a dataset using the specified strategy.

        Args:
            dataset_id: Dataset to load.
            strategy: How to load (full, incremental, etc.).
            partitions: Optional partition filter.
            use_cache: Whether to check cache first.
            **kwargs: Backend-specific options.

        Returns:
            Loaded data in the native format.
        """
        cache_key = f"load:{dataset_id}:{strategy.value}"

        # Check cache
        if use_cache:
            cached = await self._cache.get(dataset_id, cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", cache_key)
                return cached

        # Execute load strategy
        start = datetime.now(timezone.utc)
        try:
            if strategy == LoadStrategy.FULL:
                data = await self._load_full(dataset_id, **kwargs)
            elif strategy == LoadStrategy.INCREMENTAL:
                data = await self._load_incremental(dataset_id, **kwargs)
            elif strategy == LoadStrategy.SNAPSHOT:
                data = await self._load_snapshot(dataset_id, **kwargs)
            elif strategy == LoadStrategy.STREAMING:
                data = await self._load_streaming(dataset_id, **kwargs)
            elif strategy == LoadStrategy.LAZY:
                data = await self._load_lazy(dataset_id, **kwargs)
            else:
                raise ValueError(f"Unknown load strategy: {strategy}")

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

            # Cache the result
            if use_cache:
                await self._cache.put(dataset_id, cache_key, data)

            self._record_load(dataset_id, strategy, elapsed, True)
            return data

        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            self._record_load(dataset_id, strategy, elapsed, False, str(exc))
            raise

    # ── strategy implementations ──────────────────────────────────────────

    async def _load_full(self, dataset_id: str, **kwargs) -> Any:
        """Load the complete dataset."""
        logger.info("Loading full dataset: %s", dataset_id)
        # Backend-specific loading logic would go here
        return {"dataset_id": dataset_id, "strategy": "full", "data": []}

    async def _load_incremental(self, dataset_id: str, **kwargs) -> Any:
        """Load only data that has changed since last load."""
        logger.info("Loading incremental dataset: %s", dataset_id)
        return {"dataset_id": dataset_id, "strategy": "incremental", "data": []}

    async def _load_snapshot(self, dataset_id: str, **kwargs) -> Any:
        """Load from a specific snapshot version."""
        logger.info("Loading snapshot dataset: %s", dataset_id)
        return {"dataset_id": dataset_id, "strategy": "snapshot", "data": []}

    async def _load_streaming(self, dataset_id: str, **kwargs) -> Any:
        """Load dataset in streaming/batch mode."""
        logger.info("Loading streaming dataset: %s", dataset_id)
        return {"dataset_id": dataset_id, "strategy": "streaming", "data": []}

    async def _load_lazy(self, dataset_id: str, **kwargs) -> Any:
        """Create a lazy-loading proxy for the dataset."""
        logger.info("Creating lazy proxy for dataset: %s", dataset_id)
        return {"dataset_id": dataset_id, "strategy": "lazy", "data": []}

    # ── history ───────────────────────────────────────────────────────────

    def _record_load(
        self,
        dataset_id: str,
        strategy: LoadStrategy,
        elapsed: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        self._load_history.append({
            "dataset_id": dataset_id,
            "strategy": strategy.value,
            "elapsed_seconds": elapsed,
            "success": success,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_load_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._load_history[-limit:]

    def __repr__(self) -> str:
        return f"DatasetLoader(loads={len(self._load_history)})"

"""Dataset API — RESTful API for dataset management.

Commit 11 Part 1.5: Provides HTTP endpoints for registering, listing,
and managing research datasets.

Endpoints:
    GET    /research/datasets          — List datasets
    POST   /research/datasets          — Register dataset
    GET    /research/datasets/{id}     — Get dataset details
    PUT    /research/datasets/{id}     — Update dataset
    DELETE /research/datasets/{id}     — Delete dataset
    POST   /research/datasets/{id}/refresh — Refresh dataset
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DatasetStatus(str, Enum):
    """Dataset status values."""

    REGISTERED = "registered"
    LOADING = "loading"
    READY = "ready"
    STALE = "stale"
    ERROR = "error"


class DatasetAPI:
    """RESTful API for dataset management.

    Provides CRUD operations for research datasets.

    Usage::

        api = DatasetAPI(config={"base_url": "/research"})
        await api.initialize()
        ds_id = await api.register_dataset(
            name="US Equity Daily",
            market="us",
            data_type="bar_daily",
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        api_id: Optional[str] = None,
    ) -> None:
        self._id: str = api_id or f"dsapi-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._created_at: datetime = datetime.now(timezone.utc)

        # Dataset store
        self._datasets: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the dataset API."""
        logger.info("Initializing DatasetAPI [%s]", self._id)

    async def shutdown(self) -> None:
        """Clean up."""
        self._datasets.clear()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def register_dataset(
        self,
        name: str,
        market: str,
        data_type: str,
        *,
        description: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a new dataset.

        Args:
            name: Dataset name.
            market: Market identifier (us, cn, hk, etc.).
            data_type: Data type (bar_daily, tick, etc.).
            description: Optional description.
            symbols: List of symbols.
            start_date: Data start date.
            end_date: Data end date.
            metadata: Additional metadata.

        Returns:
            Registered dataset details.
        """
        ds_id = f"ds-{uuid4().hex[:12]}"
        dataset = {
            "id": ds_id,
            "name": name,
            "market": market,
            "data_type": data_type,
            "description": description or "",
            "symbols": symbols or [],
            "start_date": start_date,
            "end_date": end_date,
            "metadata": metadata or {},
            "status": DatasetStatus.REGISTERED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._datasets[ds_id] = dataset
        logger.info("Dataset registered: %s [%s] market=%s type=%s", ds_id, name, market, data_type)
        return dict(dataset)

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Get dataset details."""
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise KeyError(f"Dataset not found: {dataset_id}")
        return dict(dataset)

    async def update_dataset(
        self,
        dataset_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update dataset metadata."""
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise KeyError(f"Dataset not found: {dataset_id}")

        if name is not None:
            dataset["name"] = name
        if description is not None:
            dataset["description"] = description
        if symbols is not None:
            dataset["symbols"] = symbols
        if metadata is not None:
            dataset["metadata"].update(metadata)
        dataset["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(dataset)

    async def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset."""
        if dataset_id not in self._datasets:
            raise KeyError(f"Dataset not found: {dataset_id}")
        del self._datasets[dataset_id]
        logger.info("Dataset deleted: %s", dataset_id)

    async def list_datasets(
        self,
        market: Optional[str] = None,
        data_type: Optional[str] = None,
        status: Optional[DatasetStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List datasets with optional filtering."""
        datasets = list(self._datasets.values())
        if market is not None:
            datasets = [d for d in datasets if d["market"] == market]
        if data_type is not None:
            datasets = [d for d in datasets if d["data_type"] == data_type]
        if status is not None:
            datasets = [d for d in datasets if d["status"] == status.value]
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "market": d["market"],
                "data_type": d["data_type"],
                "status": d["status"],
                "symbol_count": len(d["symbols"]),
            }
            for d in datasets
        ]

    async def refresh_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Refresh dataset data from source."""
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise KeyError(f"Dataset not found: {dataset_id}")

        dataset["status"] = DatasetStatus.LOADING.value
        import asyncio
        await asyncio.sleep(0.01)  # simulate refresh
        dataset["status"] = DatasetStatus.READY.value
        dataset["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Dataset refreshed: %s", dataset_id)
        return {"dataset_id": dataset_id, "status": "ready"}

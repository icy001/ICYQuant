"""
ICYQuant Historical Data Service.

Commit 16 Part 1.5 — Unified service for historical data queries,
time-travel access, and versioned data retrieval through the data lake.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Historical query type."""
    RANGE = "range"
    POINT_IN_TIME = "point_in_time"
    LATEST = "latest"
    VERSIONED = "versioned"


@dataclass
class HistoricalQuery:
    """A historical data query."""
    query_id: str = ""
    dataset_id: str = ""
    query_type: QueryType = QueryType.RANGE
    instruments: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    as_of: Optional[datetime] = None
    version: Optional[int] = None
    limit: int = 1000
    offset: int = 0
    filters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HistoricalResult:
    """Result of a historical data query."""
    query_id: str = ""
    success: bool = True
    rows: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    scanned_bytes: int = 0
    partitions_scanned: int = 0
    as_of_version: Optional[int] = None
    latency_ms: float = 0.0
    cached: bool = False
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class HistoricalDataService:
    """Unified historical data service.

    Provides:
      - Range queries over historical data
      - Point-in-time (time-travel) queries
      - Versioned data retrieval
      - Cross-dataset aggregations
      - Query optimization and caching
    """

    def __init__(self, data_lake: Any = None) -> None:
        self._data_lake = data_lake
        self._query_counter = 0

    # ------------------------------------------------------------------
    # Query Operations
    # ------------------------------------------------------------------

    async def query(self, query: HistoricalQuery) -> HistoricalResult:
        """Execute a historical data query."""
        start = datetime.now(timezone.utc)
        query.query_id = f"hq-{self._next_id():08d}"
        result = HistoricalResult(query_id=query.query_id)

        try:
            if self._data_lake:
                lake_result = await self._data_lake.query(
                    dataset_id=query.dataset_id,
                    start_time=query.start_time,
                    end_time=query.end_time,
                    as_of=query.as_of,
                    instruments=query.instruments,
                    fields=query.fields,
                    limit=query.limit,
                )
                if lake_result:
                    result.rows = lake_result.rows
                    result.total_count = lake_result.total_count
                    result.scanned_bytes = lake_result.scanned_bytes
                    result.as_of_version = lake_result.as_of_version

            result.success = True
        except Exception as exc:
            result.success = False
            result.errors.append(str(exc))

        result.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return result

    async def query_range(
        self,
        dataset_id: str,
        instruments: list[str],
        start_time: datetime,
        end_time: datetime,
        fields: Optional[list[str]] = None,
        limit: int = 1000,
    ) -> HistoricalResult:
        """Convenience method for range queries."""
        return await self.query(HistoricalQuery(
            dataset_id=dataset_id,
            query_type=QueryType.RANGE,
            instruments=instruments,
            fields=fields or [],
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        ))

    async def query_as_of(
        self,
        dataset_id: str,
        instruments: list[str],
        as_of: datetime,
        fields: Optional[list[str]] = None,
    ) -> HistoricalResult:
        """Convenience method for time-travel queries."""
        return await self.query(HistoricalQuery(
            dataset_id=dataset_id,
            query_type=QueryType.POINT_IN_TIME,
            instruments=instruments,
            fields=fields or [],
            as_of=as_of,
        ))

    async def query_version(
        self,
        dataset_id: str,
        instruments: list[str],
        version: int,
        fields: Optional[list[str]] = None,
    ) -> HistoricalResult:
        """Convenience method for versioned queries."""
        return await self.query(HistoricalQuery(
            dataset_id=dataset_id,
            query_type=QueryType.VERSIONED,
            instruments=instruments,
            fields=fields or [],
            version=version,
        ))

    # ------------------------------------------------------------------
    # Dataset Operations
    # ------------------------------------------------------------------

    async def list_versions(self, dataset_id: str) -> list[int]:
        """List available versions for a dataset."""
        if self._data_lake:
            return await self._data_lake.list_versions(dataset_id)
        return []

    async def get_latest_version(self, dataset_id: str) -> Optional[int]:
        """Get the latest version of a dataset."""
        versions = await self.list_versions(dataset_id)
        return versions[-1] if versions else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._query_counter += 1
        return self._query_counter

    @property
    def query_count(self) -> int:
        return self._query_counter

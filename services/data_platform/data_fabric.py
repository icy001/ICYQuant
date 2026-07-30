"""ICYQuant Data Fabric.

The unified data access layer that sits on top of the lakehouse,
providing a single interface for all downstream consumers:

    Feature Store → Data Fabric → Lakehouse
    AI Platform   → Data Fabric → Lakehouse
    Trading       → Data Fabric → Lakehouse

Ensures "Single Source of Truth" across the entire platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.data_platform.lakehouse import (
    DataLakehouse,
    DatasetType,
    WriteMode,
    DataFile,
    TableSnapshot,
)
from services.data_platform.config import (
    LakehouseConfig,
    StorageTier,
    QualityConfig,
)
from services.data_platform.quality_engine import QualityEngine, QualityReport
from services.data_platform.lineage import LineageTracker, LineageNode, LineageEdge


# ============================================================================
# Data Fabric Types
# ============================================================================


class FabricAccessPattern(str, Enum):
    """Access patterns for data fabric consumers."""

    BATCH_READ = "batch_read"         # Large historical reads
    STREAMING = "streaming"           # Real-time streaming reads
    POINT_QUERY = "point_query"       # Single record lookups
    ANALYTICAL = "analytical"         # Aggregation / analytical queries


@dataclass
class FabricQuery:
    """A query through the data fabric."""

    dataset: str
    consumer: str
    access_pattern: FabricAccessPattern = FabricAccessPattern.BATCH_READ
    as_of: Optional[datetime] = None
    partition: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: Optional[int] = None
    columns: Optional[List[str]] = None
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FabricWriteRequest:
    """A write request through the data fabric."""

    dataset: str
    data: List[Dict[str, Any]]
    producer: str
    mode: WriteMode = WriteMode.APPEND
    partition: Optional[str] = None
    validate_quality: bool = True
    track_lineage: bool = True
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FabricResult:
    """Result from a data fabric operation."""

    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    rows_affected: int = 0
    quality_report: Optional[QualityReport] = None
    lineage_nodes: List[LineageNode] = field(default_factory=list)
    error: Optional[str] = None
    request_id: str = ""


@dataclass
class DataView:
    """A logical view over lakehouse data."""

    name: str
    dataset: str
    description: str = ""
    filters: Dict[str, Any] = field(default_factory=dict)
    columns: List[str] = field(default_factory=list)
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Data Fabric Core
# ============================================================================


class DataFabric:
    """Unified Data Fabric for ICYQuant.

    Acts as the single entry point for all data access across the platform.
    Enforces quality checks, lineage tracking, and access control on every
    read and write operation.

    Usage::

        fabric = DataFabric(lakehouse, quality_engine, lineage_tracker)
        result = fabric.query(FabricQuery(dataset="market_tick", consumer="research"))
        result = fabric.write(FabricWriteRequest(
            dataset="features", data=[...], producer="feature_pipeline"
        ))
    """

    def __init__(
        self,
        lakehouse: DataLakehouse,
        quality_engine: Optional[QualityEngine] = None,
        lineage_tracker: Optional[LineageTracker] = None,
        config: Optional[LakehouseConfig] = None,
    ) -> None:
        self.lakehouse = lakehouse
        self.quality_engine = quality_engine
        self.lineage_tracker = lineage_tracker
        self.config = config or LakehouseConfig()

        self._views: Dict[str, DataView] = {}
        self._pre_hooks: List[Callable[[FabricQuery], Optional[FabricQuery]]] = []
        self._post_hooks: List[Callable[[FabricResult], FabricResult]] = []
        self._access_stats: Dict[str, Dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Query Operations
    # ------------------------------------------------------------------

    def query(self, query: FabricQuery) -> FabricResult:
        """Execute a query through the data fabric.

        Args:
            query: FabricQuery specification.

        Returns:
            FabricResult with data and metadata.
        """
        # Run pre-hooks (validation, access control, etc.)
        for hook in self._pre_hooks:
            result = hook(query)
            if result is not None:
                query = result

        try:
            # Execute against lakehouse
            data = self.lakehouse.read(
                dataset=query.dataset,
                as_of=query.as_of,
                partition=query.partition,
                limit=query.limit,
            )

            # Apply column projection
            if query.columns:
                data = [
                    {col: row.get(col) for col in query.columns if col in row}
                    for row in data
                ]

            # Apply filters
            for key, value in query.filters.items():
                data = [row for row in data if row.get(key) == value]

            # Track access statistics
            self._track_access(query.consumer, query.dataset, "read", len(data))

            # Track lineage
            lineage_nodes: List[LineageNode] = []
            if self.lineage_tracker:
                lineage_nodes = self.lineage_tracker.get_lineage(query.dataset)

            return FabricResult(
                success=True,
                data=data,
                rows_affected=len(data),
                lineage_nodes=lineage_nodes,
                request_id=query.request_id,
            )

        except Exception as e:
            return FabricResult(
                success=False,
                error=str(e),
                request_id=query.request_id,
            )

    def query_sql(self, sql: str, consumer: str = "default") -> FabricResult:
        """Execute a SQL-like query through the data fabric.

        Args:
            sql: SQL query string.
            consumer: Consumer identifier for tracking.

        Returns:
            FabricResult with data.
        """
        try:
            data = self.lakehouse.read_sql(sql)

            # Extract dataset name for tracking
            parts = sql.strip().split()
            from_idx = next((i for i, p in enumerate(parts) if p.upper() == "FROM"), None)
            dataset = parts[from_idx + 1].rstrip(";") if from_idx else "unknown"

            self._track_access(consumer, dataset, "read", len(data))

            return FabricResult(
                success=True,
                data=data,
                rows_affected=len(data),
            )
        except Exception as e:
            return FabricResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    def write(self, request: FabricWriteRequest) -> FabricResult:
        """Write data through the data fabric.

        Applies quality checks and lineage tracking before/after writing.

        Args:
            request: FabricWriteRequest specification.

        Returns:
            FabricResult with write metadata.
        """
        try:
            # Quality check before write
            quality_report: Optional[QualityReport] = None
            if request.validate_quality and self.quality_engine:
                quality_report = self.quality_engine.validate(
                    request.dataset, request.data
                )
                if quality_report.status == "failed":
                    return FabricResult(
                        success=False,
                        error=f"Quality check failed: {quality_report.summary}",
                        quality_report=quality_report,
                        request_id=request.request_id,
                    )

            # Write to lakehouse
            data_file = self.lakehouse.write(
                dataset=request.dataset,
                data=request.data,
                mode=request.mode,
                partition=request.partition,
            )

            # Track lineage
            lineage_nodes: List[LineageNode] = []
            if request.track_lineage and self.lineage_tracker:
                self.lineage_tracker.add_node(
                    dataset=request.dataset,
                    producer=request.producer,
                    operation="write",
                    row_count=len(request.data),
                )
                lineage_nodes = self.lineage_tracker.get_lineage(request.dataset)

            # Track access
            self._track_access(request.producer, request.dataset, "write", len(request.data))

            return FabricResult(
                success=True,
                rows_affected=len(request.data),
                quality_report=quality_report,
                lineage_nodes=lineage_nodes,
                request_id=request.request_id,
            )

        except Exception as e:
            return FabricResult(
                success=False,
                error=str(e),
                request_id=request.request_id,
            )

    # ------------------------------------------------------------------
    # View Management
    # ------------------------------------------------------------------

    def create_view(self, view: DataView) -> DataView:
        """Create a logical view over lakehouse data.

        Views provide filtered/projected access to datasets without
        duplicating data.

        Args:
            view: DataView definition.

        Returns:
            The created DataView.
        """
        self._views[view.name] = view
        return view

    def get_view(self, name: str) -> Optional[DataView]:
        """Get a view by name."""
        return self._views.get(name)

    def query_view(self, view_name: str, consumer: str = "default") -> FabricResult:
        """Query data through a named view.

        Args:
            view_name: View name.
            consumer: Consumer identifier.

        Returns:
            FabricResult with filtered/projected data.
        """
        view = self._views.get(view_name)
        if not view:
            return FabricResult(success=False, error=f"View '{view_name}' not found")

        return self.query(FabricQuery(
            dataset=view.dataset,
            consumer=consumer,
            filters=view.filters,
            columns=view.columns,
        ))

    # ------------------------------------------------------------------
    # Access Statistics
    # ------------------------------------------------------------------

    def _track_access(
        self, consumer: str, dataset: str, operation: str, rows: int
    ) -> None:
        """Track data access statistics."""
        key = f"{consumer}:{dataset}"
        if key not in self._access_stats:
            self._access_stats[key] = {
                "consumer": consumer,
                "dataset": dataset,
                "reads": 0,
                "writes": 0,
                "total_rows_read": 0,
                "total_rows_written": 0,
                "last_access": "",
            }

        stats = self._access_stats[key]
        if operation == "read":
            stats["reads"] += 1
            stats["total_rows_read"] += rows
        else:
            stats["writes"] += 1
            stats["total_rows_written"] += rows
        stats["last_access"] = datetime.utcnow().isoformat()

    def get_access_stats(self) -> List[Dict[str, Any]]:
        """Get data access statistics."""
        return list(self._access_stats.values())

    def get_consumer_stats(self, consumer: str) -> List[Dict[str, Any]]:
        """Get access statistics for a specific consumer."""
        return [
            v for v in self._access_stats.values()
            if v["consumer"] == consumer
        ]

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def add_pre_hook(self, hook: Callable[[FabricQuery], Optional[FabricQuery]]) -> None:
        """Add a pre-query hook for validation/transformation."""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable[[FabricResult], FabricResult]) -> None:
        """Add a post-query hook for enrichment/auditing."""
        self._post_hooks.append(hook)

    # ------------------------------------------------------------------
    # Snapshot & Time Travel
    # ------------------------------------------------------------------

    def create_snapshot(self, dataset: str, description: str = "") -> TableSnapshot:
        """Create a snapshot of a dataset through the fabric."""
        return self.lakehouse.create_snapshot(dataset, description)

    def query_as_of(
        self, dataset: str, timestamp: datetime, consumer: str = "default"
    ) -> FabricResult:
        """Time-travel query: read data as it existed at timestamp.

        Args:
            dataset: Dataset name.
            timestamp: Point-in-time to query.
            consumer: Consumer identifier.

        Returns:
            FabricResult with historical data.
        """
        return self.query(FabricQuery(
            dataset=dataset,
            consumer=consumer,
            as_of=timestamp,
        ))

    def get_lakehouse_stats(self) -> Dict[str, Any]:
        """Get lakehouse storage statistics."""
        return self.lakehouse.get_storage_stats()

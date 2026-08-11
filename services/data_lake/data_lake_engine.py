"""
Data Lake Engine — central orchestrator for the enterprise historical
data lake with versioned storage, time-travel queries, and replay.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from .data_lake_runtime import DataLakeRuntime, DataLakeRuntimeConfig, DataLakeRuntimeStatus
from .diagnostics import DataLakeDiagnostics
from .health import DataLakeHealthChecker, HealthStatus
from .metrics import DataLakeMetrics
from .storage_manager import StorageManager, StorageBackend
from .dataset_registry import DatasetRegistry
from .metadata_catalog import MetadataCatalog
from .snapshot_manager import SnapshotManager
from .version_manager import VersionManager
from .replay_engine import ReplayEngine, ReplayConfig
from .time_travel_query import TimeTravelQuery, TimeTravelConfig
from .historical_query_engine import HistoricalQueryEngine

logger = logging.getLogger(__name__)


class DataLakeState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DataLakeConfig:
    lake_id: str = "icyquant-data-lake"
    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_base_path: str = "data/lake"
    runtime: DataLakeRuntimeConfig = field(default_factory=DataLakeRuntimeConfig)
    replay: ReplayConfig = field(default_factory=ReplayConfig)
    time_travel: TimeTravelConfig = field(default_factory=TimeTravelConfig)

    metrics_enabled: bool = True
    telemetry_enabled: bool = True
    health_check_interval: float = 15.0

    max_concurrent_ingests: int = 8
    max_concurrent_queries: int = 16
    ingest_queue_size: int = 50_000
    graceful_shutdown_timeout: float = 30.0


class DataLakeEngine:
    """
    Central orchestrator for the Historical Data Lake.

    Coordinates ingestion, storage, versioning, replay, and time-travel
    queries across all datasets.

    Usage::

        lake = DataLakeEngine()
        await lake.initialize(config)
        await lake.start()

        # Ingest market data
        await lake.ingest("equity_ticks", canonical_records)

        # Time-travel query
        records = await lake.query_time_travel(
            "equity_ticks", as_of=datetime(2025, 1, 15, tzinfo=timezone.utc)
        )

        # Replay for backtest
        async for event in lake.replay("equity_ticks", start, end):
            strategy.on_market_data(event)

        await lake.stop()
    """

    def __init__(self, config: Optional[DataLakeConfig] = None) -> None:
        self.config = config or DataLakeConfig()
        self._state = DataLakeState.CREATED

        # Subsystems (initialized later)
        self._runtime: Optional[DataLakeRuntime] = None
        self._storage: Optional[StorageManager] = None
        self._datasets: Optional[DatasetRegistry] = None
        self._catalog: Optional[MetadataCatalog] = None
        self._snapshots: Optional[SnapshotManager] = None
        self._versions: Optional[VersionManager] = None
        self._replay_engine: Optional[ReplayEngine] = None
        self._time_travel: Optional[TimeTravelQuery] = None
        self._query_engine: Optional[HistoricalQueryEngine] = None
        self._metrics: Optional[DataLakeMetrics] = None
        self._diagnostics: Optional[DataLakeDiagnostics] = None
        self._health: Optional[DataLakeHealthChecker] = None

        self._ingest_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

    # ── Lifecycle ───────────────────────────────────

    async def initialize(self, config: Optional[DataLakeConfig] = None) -> None:
        if config:
            self.config = config
        self._state = DataLakeState.INITIALIZING
        logger.info("Initializing Data Lake Engine: %s", self.config.lake_id)

        self._metrics = DataLakeMetrics()
        self._diagnostics = DataLakeDiagnostics()
        self._health = DataLakeHealthChecker()

        self._runtime = DataLakeRuntime(self.config.runtime)
        await self._runtime.initialize()

        self._storage = StorageManager(
            backend=self.config.storage_backend,
            base_path=self.config.storage_base_path,
        )
        await self._storage.initialize()

        self._datasets = DatasetRegistry()
        self._catalog = MetadataCatalog(self._storage, self._datasets)
        self._snapshots = SnapshotManager(self._storage, self._catalog)
        self._versions = VersionManager(self._storage, self._catalog)

        self._replay_engine = ReplayEngine(
            self._storage, self._catalog, self.config.replay
        )
        self._time_travel = TimeTravelQuery(
            self._storage, self._catalog, self._versions, self.config.time_travel
        )
        self._query_engine = HistoricalQueryEngine(self._storage, self._catalog)

        self._state = DataLakeState.STOPPED
        logger.info("Data Lake Engine initialized")

    async def start(self) -> None:
        self._state = DataLakeState.RUNNING
        if self._runtime:
            await self._runtime.start()
        if self._storage:
            await self._storage.start()
        if self._replay_engine:
            await self._replay_engine.start()
        self._metrics.record_state_transition(self._state)
        logger.info("Data Lake Engine started")

    async def stop(self) -> None:
        self._state = DataLakeState.STOPPING
        self._shutdown_event.set()

        subsystems = [
            ("replay_engine", self._replay_engine),
            ("time_travel", self._time_travel),
            ("snapshots", self._snapshots),
            ("versions", self._versions),
            ("storage", self._storage),
            ("runtime", self._runtime),
        ]
        for name, sub in subsystems:
            if sub and hasattr(sub, "stop"):
                try:
                    await asyncio.wait_for(
                        sub.stop(), timeout=self.config.graceful_shutdown_timeout / len(subsystems)
                    )
                except asyncio.TimeoutError:
                    logger.warning("Timeout stopping %s", name)

        self._state = DataLakeState.STOPPED
        logger.info("Data Lake Engine stopped")

    @property
    def state(self) -> DataLakeState:
        return self._state

    # ── Ingestion ───────────────────────────────────

    async def ingest(
        self,
        dataset_name: str,
        records: list[Any],
        *,
        partition: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Ingest a batch of canonical records into the data lake.

        Returns the version identifier for this ingestion.
        """
        if self._state != DataLakeState.RUNNING:
            raise RuntimeError(f"Engine not running: {self._state}")

        async with self._ingest_lock:
            start_time = datetime.now(timezone.utc)

            dataset = await self._datasets.get_or_create(dataset_name)

            version = await self._versions.create_version(dataset.name, metadata=metadata)

            storage_path = await self._storage.write_batch(
                dataset=dataset,
                records=records,
                partition=partition,
                version_id=version.version_id,
            )

            await self._catalog.register_ingestion(
                dataset=dataset,
                version=version,
                storage_path=storage_path,
                record_count=len(records),
                partition=partition,
            )

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._metrics.record_ingest(dataset.name, len(records), elapsed)
            logger.info(
                "Ingested %d records into %s (v%s) in %.3fs",
                len(records), dataset.name, version.version_id, elapsed,
            )

            return version.version_id

    async def ingest_stream(
        self, dataset_name: str, stream: AsyncIterator[Any], *, partition: Optional[str] = None
    ) -> list[str]:
        """Ingest from an async stream, batching internally."""
        version_ids: list[str] = []
        batch: list[Any] = []
        batch_size = 10_000

        async for record in stream:
            batch.append(record)
            if len(batch) >= batch_size:
                vid = await self.ingest(dataset_name, batch, partition=partition)
                version_ids.append(vid)
                batch.clear()

        if batch:
            vid = await self.ingest(dataset_name, batch, partition=partition)
            version_ids.append(vid)

        return version_ids

    # ── Query ───────────────────────────────────────

    async def query(
        self,
        dataset_name: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 10_000,
    ) -> list[Any]:
        """Execute a historical query against a dataset."""
        return await self._query_engine.query(
            dataset_name, start=start, end=end, filters=filters, limit=limit
        )

    async def query_time_travel(
        self, dataset_name: str, as_of: datetime, *, filters: Optional[dict[str, Any]] = None
    ) -> list[Any]:
        """Query dataset as it existed at a specific point in time."""
        return await self._time_travel.query_as_of(dataset_name, as_of, filters=filters)

    async def query_version(
        self, dataset_name: str, version_id: str, *, filters: Optional[dict[str, Any]] = None
    ) -> list[Any]:
        """Query a specific version of a dataset."""
        return await self._query_engine.query_version(dataset_name, version_id, filters=filters)

    # ── Replay ──────────────────────────────────────

    async def replay(
        self,
        dataset_name: str,
        start: datetime,
        end: datetime,
        *,
        speed: float = 1.0,
        checkpoint: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        """
        Replay historical market data as a real-time stream.

        Args:
            dataset_name: Dataset to replay.
            start: Start of replay window.
            end: End of replay window.
            speed: Replay speed multiplier (1.0 = real-time).
            checkpoint: Resume from a saved checkpoint.

        Yields:
            Market data events in chronological order.
        """
        async for event in self._replay_engine.replay(
            dataset_name, start, end, speed=speed, checkpoint=checkpoint
        ):
            yield event

    async def create_snapshot(
        self, dataset_name: str, *, label: Optional[str] = None
    ) -> str:
        """Create a named snapshot of the current dataset state."""
        return await self._snapshots.create_snapshot(dataset_name, label=label)

    async def restore_snapshot(self, snapshot_id: str) -> None:
        """Restore a dataset to a previous snapshot."""
        await self._snapshots.restore(snapshot_id)

    async def list_snapshots(self, dataset_name: str) -> list[dict[str, Any]]:
        return await self._snapshots.list_snapshots(dataset_name)

    async def list_versions(self, dataset_name: str) -> list[dict[str, Any]]:
        return await self._versions.list_versions(dataset_name)

    async def get_statistics(self, dataset_name: str) -> dict[str, Any]:
        return await self._catalog.get_statistics(dataset_name)

    async def health_check(self) -> dict[str, Any]:
        if self._health:
            return await self._health.check()
        return {"status": "not_initialized"}

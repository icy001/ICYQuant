"""
Data Lake Manager — lifecycle coordination and administrative operations
for the historical data lake.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .data_lake_engine import DataLakeEngine, DataLakeConfig, DataLakeState

logger = logging.getLogger(__name__)


class ManagerState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ManagerConfig:
    manager_id: str = "icyquant-datalake-manager"
    engine: DataLakeConfig = field(default_factory=DataLakeConfig)
    auto_compact_interval_hours: int = 24
    auto_snapshot_interval_hours: int = 6
    auto_cleanup_enabled: bool = True
    maintenance_window: Optional[tuple[int, int]] = None  # (hour_start, hour_end) UTC


class DataLakeManager:
    """
    Administrative lifecycle manager for the Data Lake Engine.

    Handles startup, shutdown, scheduled maintenance (compaction,
    snapshotting, cleanup), and operational commands.
    """

    def __init__(self, config: Optional[ManagerConfig] = None) -> None:
        self.config = config or ManagerConfig()
        self._state = ManagerState.CREATED
        self._engine: Optional[DataLakeEngine] = None
        self._maintenance_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        self._state = ManagerState.INITIALIZING
        self._engine = DataLakeEngine(self.config.engine)
        await self._engine.initialize()
        self._state = ManagerState.STOPPED
        logger.info("Data Lake Manager initialized")

    async def start(self) -> None:
        if not self._engine:
            raise RuntimeError("Manager not initialized")
        self._state = ManagerState.ACTIVE
        await self._engine.start()
        self._shutdown_event.clear()
        if self.config.auto_snapshot_interval_hours > 0:
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        logger.info("Data Lake Manager started")

    async def stop(self) -> None:
        self._state = ManagerState.STOPPING
        self._shutdown_event.set()
        if self._maintenance_task:
            self._maintenance_task.cancel()
        if self._engine:
            await self._engine.stop()
        self._state = ManagerState.STOPPED
        logger.info("Data Lake Manager stopped")

    async def pause(self) -> None:
        if self._engine:
            self._engine._state = DataLakeState.PAUSED
        self._state = ManagerState.PAUSED

    async def resume(self) -> None:
        if self._engine:
            self._engine._state = DataLakeState.RUNNING
        self._state = ManagerState.ACTIVE

    # ── Maintenance ─────────────────────────────────

    async def _maintenance_loop(self) -> None:
        snapshot_interval = self.config.auto_snapshot_interval_hours * 3600
        compact_interval = self.config.auto_compact_interval_hours * 3600
        last_snapshot = datetime.now(timezone.utc)
        last_compact = datetime.now(timezone.utc)

        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)

            if (now - last_snapshot).total_seconds() >= snapshot_interval:
                await self._run_scheduled_snapshots()
                last_snapshot = now

            if self.config.auto_cleanup_enabled and (now - last_compact).total_seconds() >= compact_interval:
                await self._run_compaction()
                last_compact = now

    async def _run_scheduled_snapshots(self) -> None:
        if not self._engine:
            return
        try:
            logger.info("Running scheduled snapshots")
            # Iterate datasets and snapshot — simplified for now
        except Exception:
            logger.exception("Scheduled snapshot failed")

    async def _run_compaction(self) -> None:
        try:
            logger.info("Running scheduled compaction")
            # Trigger compaction on storage manager
        except Exception:
            logger.exception("Scheduled compaction failed")

    # ── Administrative Commands ─────────────────────

    async def list_datasets(self) -> list[dict[str, Any]]:
        if not self._engine or not self._engine._datasets:
            return []
        return await self._engine._datasets.list_all()

    async def get_dataset_info(self, name: str) -> Optional[dict[str, Any]]:
        if not self._engine:
            return None
        try:
            stats = await self._engine.get_statistics(name)
            versions = await self._engine.list_versions(name)
            return {"name": name, "statistics": stats, "version_count": len(versions)}
        except Exception:
            return None

    async def delete_dataset(self, name: str) -> bool:
        if not self._engine or not self._engine._datasets:
            return False
        return await self._engine._datasets.delete(name)

    async def compact_dataset(self, name: str) -> None:
        if not self._engine or not self._engine._storage:
            return
        await self._engine._storage.compact(name)
        logger.info("Compacted dataset: %s", name)

    @property
    def state(self) -> ManagerState:
        return self._state

    @property
    def engine(self) -> Optional[DataLakeEngine]:
        return self._engine

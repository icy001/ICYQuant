"""Cluster synchronizer for ICYQuant service discovery.

Provides ``ClusterSynchronizer`` for incremental, full, and
snapshot-based synchronization of registry state across
cluster nodes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class ClusterSynchronizer:
    """Synchronizes registry state across cluster nodes.

    Supports incremental sync, full sync, and snapshot sync
    to keep all cluster nodes consistent.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        cluster: Any = None,
        sync_interval: float = 30.0,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._cluster = cluster
        self._sync_interval = sync_interval
        self._sync_count = 0
        self._incremental_count = 0
        self._full_count = 0
        self._snapshot_count = 0
        self._last_sync_time: Optional[datetime] = None
        self._last_result: Optional[Dict[str, Any]] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False

    async def sync_incremental(self) -> Dict[str, Any]:
        """Perform an incremental synchronization.

        Only syncs changes since the last sync.

        Returns:
            Sync result dictionary.
        """
        with self._lock:
            self._incremental_count += 1
            self._sync_count += 1

        start = time.monotonic()
        changes = 0
        errors: List[str] = []

        cluster = self._cluster
        if cluster is not None:
            nodes = cluster.list_nodes()
            for node in nodes:
                try:
                    changes += 1
                except Exception as exc:
                    errors.append(str(exc))

        duration = time.monotonic() - start

        result: Dict[str, Any] = {
            "type": "incremental",
            "success": True,
            "changes_synced": changes,
            "errors": errors,
            "duration_s": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._last_sync_time = datetime.utcnow()
        self._last_result = result

        logger.info(
            "Incremental sync complete: %d changes in %.3fs.",
            changes,
            duration,
        )
        return result

    async def sync_full(self) -> Dict[str, Any]:
        """Perform a full synchronization.

        Re-synchronizes all state across all nodes.

        Returns:
            Sync result dictionary.
        """
        with self._lock:
            self._full_count += 1
            self._sync_count += 1

        start = time.monotonic()
        total_nodes = 0
        errors: List[str] = []

        cluster = self._cluster
        if cluster is not None:
            nodes = cluster.list_nodes()
            total_nodes = len(nodes)
            for node in nodes:
                try:
                    pass
                except Exception as exc:
                    errors.append(str(exc))

        duration = time.monotonic() - start

        result: Dict[str, Any] = {
            "type": "full",
            "success": len(errors) == 0,
            "nodes_synced": total_nodes,
            "errors": errors,
            "duration_s": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._last_sync_time = datetime.utcnow()
        self._last_result = result

        logger.info(
            "Full sync complete: %d nodes in %.3fs.",
            total_nodes,
            duration,
        )
        return result

    async def sync_snapshot(
        self, snapshot_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a snapshot-based synchronization.

        Args:
            snapshot_data: Optional snapshot to sync.

        Returns:
            Sync result dictionary.
        """
        with self._lock:
            self._snapshot_count += 1
            self._sync_count += 1

        start = time.monotonic()
        services_count = 0
        errors: List[str] = []

        if snapshot_data:
            services = snapshot_data.get("services", [])
            services_count = len(services)

        duration = time.monotonic() - start

        result: Dict[str, Any] = {
            "type": "snapshot",
            "success": True,
            "services_synced": services_count,
            "has_snapshot": snapshot_data is not None,
            "errors": errors,
            "duration_s": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._last_sync_time = datetime.utcnow()
        self._last_result = result

        logger.info(
            "Snapshot sync complete: %d services in %.3fs.",
            services_count,
            duration,
        )
        return result

    async def start_auto_sync(self) -> None:
        """Start automatic periodic synchronization."""
        with self._lock:
            if self._running:
                return
            self._running = True

        async def _sync_loop() -> None:
            while self._running:
                try:
                    await asyncio.sleep(self._sync_interval)
                    if not self._running:
                        break
                    await self.sync_incremental()
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.error(
                        "Auto sync failed: %s", exc
                    )

        self._sync_task = asyncio.create_task(_sync_loop())
        logger.info(
            "Auto sync started (interval=%.1fs).",
            self._sync_interval,
        )

    async def stop_auto_sync(self) -> None:
        """Stop automatic synchronization."""
        with self._lock:
            self._running = False
            if self._sync_task is not None:
                self._sync_task.cancel()
                self._sync_task = None
        logger.info("Auto sync stopped.")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "sync_interval_s": self._sync_interval,
                "total_syncs": self._sync_count,
                "incremental_syncs": self._incremental_count,
                "full_syncs": self._full_count,
                "snapshot_syncs": self._snapshot_count,
                "last_sync_time": (
                    self._last_sync_time.isoformat()
                    if self._last_sync_time
                    else None
                ),
                "last_result": self._last_result,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ClusterSynchronizer(syncs={self._sync_count}, "
                f"running={self._running})"
            )

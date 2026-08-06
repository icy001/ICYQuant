"""Cluster Synchronization — synchronizes metadata and configuration across nodes.

Synchronizes:

* Cluster Metadata — node lists, roles, capabilities
* Configuration — cluster-wide settings and policies
* Workflow Version — version registry across nodes
* Policies — scheduling, routing, and failover policies
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClusterSynchronizer:
    """Synchronizes cluster metadata and configuration.

    Usage::

        sync = ClusterSynchronizer(interval_seconds=10.0)
        await sync.start()
        state = await sync.sync()
    """

    def __init__(self, *, interval_seconds: float = 10.0) -> None:
        self._interval = interval_seconds
        self._lock = threading.RLock()
        self._started = False
        self._last_sync: Optional[datetime] = None
        self._sync_count = 0

        # Synchronized state
        self._metadata: Dict[str, Any] = {}
        self._configuration: Dict[str, Any] = {}
        self._workflow_versions: Dict[str, List[str]] = {}  # workflow_id → versions
        self._policies: Dict[str, Any] = {}

        # Background task
        self._sync_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("ClusterSynchronizer: started (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        self._started = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("ClusterSynchronizer: stopped")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync(self) -> Dict[str, Any]:
        """Perform a full synchronization cycle."""
        with self._lock:
            self._last_sync = datetime.utcnow()
            self._sync_count += 1

        logger.debug("ClusterSynchronizer: sync #%d", self._sync_count)

        # In production: pull metadata from cluster peers / etcd / config service
        return {
            "sync_id": self._sync_count,
            "timestamp": self._last_sync.isoformat() if self._last_sync else None,
            "metadata_keys": len(self._metadata),
            "config_keys": len(self._configuration),
            "workflow_count": len(self._workflow_versions),
            "policy_count": len(self._policies),
        }

    async def _sync_loop(self) -> None:
        """Periodic synchronization loop."""
        while self._started:
            try:
                await asyncio.sleep(self._interval)
                await self.sync()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ClusterSynchronizer: error in sync loop")

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def set_metadata(self, key: str, value: Any) -> None:
        with self._lock:
            self._metadata[key] = value

    async def get_metadata(self, key: str) -> Any:
        with self._lock:
            return self._metadata.get(key)

    async def get_all_metadata(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._metadata)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def set_config(self, key: str, value: Any) -> None:
        with self._lock:
            self._configuration[key] = value

    async def get_config(self, key: str) -> Any:
        with self._lock:
            return self._configuration.get(key)

    async def get_all_config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._configuration)

    # ------------------------------------------------------------------
    # Workflow versions
    # ------------------------------------------------------------------

    async def register_workflow_version(self, workflow_id: str, version: str) -> None:
        with self._lock:
            if workflow_id not in self._workflow_versions:
                self._workflow_versions[workflow_id] = []
            if version not in self._workflow_versions[workflow_id]:
                self._workflow_versions[workflow_id].append(version)

    async def get_workflow_versions(self, workflow_id: str) -> List[str]:
        with self._lock:
            return list(self._workflow_versions.get(workflow_id, []))

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    async def set_policy(self, name: str, policy: Dict[str, Any]) -> None:
        with self._lock:
            self._policies[name] = policy

    async def get_policy(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._policies.get(name)

    async def list_policies(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._policies)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sync_count": self._sync_count,
                "last_sync": self._last_sync.isoformat() if self._last_sync else None,
                "interval_seconds": self._interval,
                "metadata_count": len(self._metadata),
                "config_count": len(self._configuration),
                "workflow_version_count": len(self._workflow_versions),
                "policy_count": len(self._policies),
            }

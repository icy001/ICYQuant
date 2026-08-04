"""
Feature flag platform synchronization.

Provides multi-instance synchronization
for feature flag deployments, ensuring
cluster-wide consistency through snapshot
sharing and version comparison.

Sync Flow:
    Admin Console → EventBus → Feature Snapshot
        → All Runtime Nodes → Consistent State
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .events import EventBus, FeatureEvent, FeatureEventType
from .runtime import RuntimeFeatureService
from .snapshot import FeatureSnapshot, SnapshotManager

logger = logging.getLogger(__name__)


class SynchronizationManager:
    """
    Manages multi-instance feature flag synchronization.

    Ensures that all runtime nodes in a cluster
    stay in sync with the latest feature flag
    configuration through event-based propagation
    and version comparison.

    Guarantees:
        - Cluster consistency
        - Snapshot version tracking
        - Eventually consistent state
        - Conflict detection

    Usage:
        sync = SynchronizationManager(bus, runtime)
        await sync.start()
        # Auto-syncs on config changes
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        runtime: Optional[RuntimeFeatureService] = None,
    ) -> None:
        """
        Initialize synchronization manager.

        Args:
            event_bus: EventBus for receiving sync events.
            runtime: RuntimeFeatureService to sync.
        """
        self._bus = event_bus or EventBus()
        self._runtime = runtime or RuntimeFeatureService()
        self._sync_count = 0
        self._conflict_count = 0
        self._last_sync_time: Optional[datetime] = None
        self._sync_history: List[Dict[str, Any]] = []

    @property
    def runtime(self) -> RuntimeFeatureService:
        """Get the runtime service."""
        return self._runtime

    async def start(self) -> None:
        """
        Start synchronization.

        Subscribes to snapshot events and
        automatically syncs the runtime when
        new snapshots are activated.
        """
        await self._bus.subscribe(
            FeatureEventType.SNAPSHOT_ACTIVATED,
            self._on_snapshot_activated,
        )
        await self._bus.subscribe(
            FeatureEventType.HOT_RELOAD,
            self._on_snapshot_activated,
        )
        logger.info("Synchronization manager started")

    async def _on_snapshot_activated(self, event: FeatureEvent) -> None:
        """
        Handle snapshot activation event.

        Args:
            event: The snapshot event.
        """
        version = event.data.get("version", 0)
        flags = event.data.get("flags", {})

        # Check for conflicts
        current_version = self._runtime.get_current_version()
        if version <= current_version:
            self._conflict_count += 1
            logger.debug(
                "Sync conflict: v%d <= current v%d",
                version,
                current_version,
            )
            return

        # Sync the runtime
        self._runtime.refresh(flags)
        self._sync_count += 1
        self._last_sync_time = datetime.utcnow()

        self._sync_history.append({
            "version": version,
            "flags_count": len(flags),
            "timestamp": self._last_sync_time.isoformat(),
            "current_version": current_version,
        })

        # Trim history
        if len(self._sync_history) > 100:
            self._sync_history = self._sync_history[-100:]

    async def sync_from_snapshot(
        self,
        snapshot: FeatureSnapshot,
    ) -> Dict[str, Any]:
        """
        Manually sync from a snapshot.

        Args:
            snapshot: Snapshot to sync from.

        Returns:
            Sync result.
        """
        current_version = self._runtime.get_current_version()

        if snapshot.version <= current_version:
            self._conflict_count += 1
            return {
                "success": False,
                "reason": "version_not_newer",
                "snapshot_version": snapshot.version,
                "current_version": current_version,
            }

        self._runtime.refresh(snapshot.flags)
        self._sync_count += 1
        self._last_sync_time = datetime.utcnow()

        return {
            "success": True,
            "snapshot_version": snapshot.version,
            "current_version": current_version,
            "flags_count": len(snapshot.flags),
        }

    async def sync_from_data(
        self,
        flags: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Manually sync from raw flag data.

        Args:
            flags: Flag data dictionary.

        Returns:
            Sync result.
        """
        self._runtime.refresh(flags)
        self._sync_count += 1
        self._last_sync_time = datetime.utcnow()

        return {
            "success": True,
            "flags_count": len(flags),
            "version": self._runtime.get_current_version(),
        }

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        current_version = self._runtime.get_current_version()
        return {
            "current_version": current_version,
            "sync_count": self._sync_count,
            "conflict_count": self._conflict_count,
            "last_sync_time": (
                self._last_sync_time.isoformat()
                if self._last_sync_time
                else None
            ),
            "runtime_flags_count": len(
                self._runtime._current_flags
            ),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        return {
            "sync_count": self._sync_count,
            "conflict_count": self._conflict_count,
            "last_sync_time": (
                self._last_sync_time.isoformat()
                if self._last_sync_time
                else None
            ),
            "sync_history_length": len(self._sync_history),
            "runtime_stats": self._runtime.get_stats(),
        }

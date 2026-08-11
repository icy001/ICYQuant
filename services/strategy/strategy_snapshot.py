"""
Strategy Snapshot Manager — state preservation for production strategies.

Captures the full runtime state of a strategy at a point in time,
enabling recovery, inspection, and audit capabilities.

Snapshot contents:
    - Runtime state (variables, counters, heartbeats)
    - Registry metadata (state, version, timestamps)
    - Configuration at time of snapshot
    - Timestamp and label for identification
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SnapshotStatus(str, Enum):
    """Status of a snapshot."""
    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"


@dataclass
class StrategySnapshot:
    """A point-in-time capture of a strategy's complete runtime state."""

    snapshot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    strategy_id: str = ""
    status: SnapshotStatus = SnapshotStatus.CREATING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Label
    label: str = ""
    description: str = ""

    # Version info
    strategy_version: str = ""
    engine_version: str = ""

    # State capture
    lifecycle_state: str = ""
    runtime_state: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Integrity
    checksum: str = ""
    size_bytes: int = 0

    # Tags
    tags: List[str] = field(default_factory=list)

    def compute_checksum(self) -> str:
        """Compute integrity checksum over snapshot contents."""
        canonical = json.dumps({
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "lifecycle_state": self.lifecycle_state,
            "runtime_state": self.runtime_state,
            "variables": self.variables,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
        }, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify snapshot integrity via checksum."""
        current = self.compute_checksum()
        return current == self.checksum

    def finalize(self) -> None:
        """Finalize the snapshot (compute checksum & size)."""
        self.checksum = self.compute_checksum()
        # Estimate size from serialized content
        serialized = json.dumps({
            "runtime_state": self.runtime_state,
            "variables": self.variables,
            "config": self.config,
            "metadata": self.metadata,
        }, default=str)
        self.size_bytes = len(serialized.encode())
        self.status = SnapshotStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "label": self.label,
            "strategy_version": self.strategy_version,
            "engine_version": self.engine_version,
            "lifecycle_state": self.lifecycle_state,
            "checksum": self.checksum[:16] + "...",
            "size_bytes": self.size_bytes,
            "tags": self.tags,
            "config": self.config,
            "metadata": self.metadata,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Full serialization including runtime state for recovery."""
        return {
            **self.to_dict(),
            "runtime_state": self.runtime_state,
            "variables": self.variables,
        }


@dataclass
class SnapshotConfig:
    """Configuration for the snapshot manager."""
    max_snapshots_per_strategy: int = 100
    snapshot_dir: str = "./data/snapshots"
    auto_snapshot_interval_minutes: int = 60
    compression_enabled: bool = True
    retention_policy: str = "fifo"  # fifo, max_count, age_based


class SnapshotManager:
    """Manager for creating and restoring strategy snapshots.

    Snapshots capture the complete runtime state of a strategy,
    enabling point-in-time recovery after failures.

    Usage:
        manager = SnapshotManager(config=SnapshotConfig())
        await manager.initialize()

        snapshot = await manager.take_snapshot("strategy_1", runtime, registry)
        snapshots = manager.list_snapshots("strategy_1")
        await manager.restore_snapshot("strategy_1", snapshot.snapshot_id, runtime)
    """

    def __init__(self, config: Optional[SnapshotConfig] = None) -> None:
        self._config = config or SnapshotConfig()
        self._lock = threading.Lock()
        self._snapshots: Dict[str, List[StrategySnapshot]] = {}  # strategy_id → snapshots
        self._initialized: bool = False
        logger.info("SnapshotManager created (max=%d/strategy)", self._config.max_snapshots_per_strategy)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("SnapshotManager initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._snapshots.clear()
        self._initialized = False
        logger.info("SnapshotManager shut down")

    # ── Snapshot Operations ──

    async def take_snapshot(
        self,
        strategy_id: str,
        runtime: Any,
        registry: Any,
        label: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> StrategySnapshot:
        """Capture a complete snapshot of a strategy's current state.

        Args:
            strategy_id: The strategy to snapshot.
            runtime: StrategyRuntime instance for runtime state.
            registry: StrategyRegistry instance for metadata.
            label: Human-readable label (e.g., "pre-deployment", "daily-close").
            description: Optional description.
            tags: Optional tags for categorization.

        Returns:
            The completed snapshot.
        """
        logger.info("Taking snapshot: %s label=%s", strategy_id, label or "auto")

        snapshot = StrategySnapshot(
            strategy_id=strategy_id,
            label=label or f"auto-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            description=description,
            tags=tags or [],
        )

        # Capture registry state
        metadata = registry.get_metadata(strategy_id)
        manifest = registry.get_manifest(strategy_id)
        if metadata:
            snapshot.lifecycle_state = metadata.state.value if hasattr(metadata.state, 'value') else str(metadata.state)
            snapshot.metadata = metadata.to_dict()
        if manifest:
            snapshot.strategy_version = manifest.version
            snapshot.config = manifest.config or {}

        # Capture runtime state
        runtime_data = runtime.get_snapshot_data(strategy_id)
        snapshot.runtime_state = runtime_data
        snapshot.variables = runtime_data.get("variables", {})

        # Finalize
        snapshot.finalize()

        # Store
        with self._lock:
            self._snapshots.setdefault(strategy_id, []).append(snapshot)
            self._enforce_retention(strategy_id)

        logger.info("Snapshot %s saved: %s (size=%d bytes, checksum=%s)",
                    snapshot.snapshot_id, strategy_id,
                    snapshot.size_bytes, snapshot.checksum[:12])
        return snapshot

    async def restore_snapshot(
        self,
        strategy_id: str,
        snapshot_id: str,
        runtime: Any,
    ) -> StrategySnapshot:
        """Restore a strategy from a snapshot.

        Args:
            strategy_id: The strategy to restore.
            snapshot_id: The snapshot ID to restore from.
            runtime: StrategyRuntime instance.

        Returns:
            The snapshot that was restored.

        Raises:
            KeyError: If snapshot not found.
            ValueError: If snapshot is corrupted or verification fails.
        """
        snapshot = self.get_snapshot(strategy_id, snapshot_id)
        if snapshot is None:
            raise KeyError(f"Snapshot not found: {snapshot_id}")

        if snapshot.status == SnapshotStatus.CORRUPTED:
            raise ValueError(f"Snapshot is corrupted: {snapshot_id}")

        if not snapshot.verify():
            snapshot.status = SnapshotStatus.CORRUPTED
            logger.error("Snapshot verification failed: %s", snapshot_id)
            raise ValueError(f"Snapshot verification failed: {snapshot_id}")

        logger.info("Restoring from snapshot %s → %s", snapshot_id, strategy_id)

        # Restore runtime state
        runtime.restore_from_snapshot(strategy_id, snapshot.to_full_dict())

        logger.info("Snapshot %s restored successfully for %s", snapshot_id, strategy_id)
        return snapshot

    # ── Queries ──

    def get_snapshot(self, strategy_id: str, snapshot_id: str) -> Optional[StrategySnapshot]:
        """Get a specific snapshot by ID."""
        if strategy_id not in self._snapshots:
            return None
        for s in self._snapshots[strategy_id]:
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def list_snapshots(
        self,
        strategy_id: str,
        limit: int = 20,
        status: Optional[SnapshotStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List snapshots for a strategy, most recent first."""
        snapshots = self._snapshots.get(strategy_id, [])
        if status:
            snapshots = [s for s in snapshots if s.status == status]
        # Most recent first
        snapshots = sorted(snapshots, key=lambda s: s.created_at, reverse=True)
        return [s.to_dict() for s in snapshots[:limit]]

    def get_latest_snapshot(self, strategy_id: str) -> Optional[StrategySnapshot]:
        """Get the most recent snapshot for a strategy."""
        snapshots = self._snapshots.get(strategy_id, [])
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.created_at)

    @property
    def total_snapshots(self) -> int:
        return sum(len(v) for v in self._snapshots.values())

    # ── Maintenance ──

    async def cleanup_strategy(self, strategy_id: str) -> int:
        """Remove all snapshots for a strategy. Returns count removed."""
        with self._lock:
            count = len(self._snapshots.get(strategy_id, []))
            self._snapshots.pop(strategy_id, None)
            logger.info("Cleaned up %d snapshots for %s", count, strategy_id)
            return count

    async def prune_old_snapshots(self, age_hours: float) -> Dict[str, int]:
        """Remove snapshots older than age_hours."""
        cutoff = datetime.now(timezone.utc).timestamp() - (age_hours * 3600)
        pruned: Dict[str, int] = {}
        with self._lock:
            for sid, snapshots in list(self._snapshots.items()):
                before = len(snapshots)
                self._snapshots[sid] = [
                    s for s in snapshots
                    if s.created_at.timestamp() >= cutoff
                ]
                removed = before - len(self._snapshots[sid])
                if removed > 0:
                    pruned[sid] = removed
        logger.info("Pruned old snapshots: %s", pruned)
        return pruned

    def _enforce_retention(self, strategy_id: str) -> None:
        """Enforce retention policy on snapshots."""
        snapshots = self._snapshots.get(strategy_id, [])
        if len(snapshots) <= self._config.max_snapshots_per_strategy:
            return

        if self._config.retention_policy == "fifo":
            # Keep most recent
            snapshots.sort(key=lambda s: s.created_at, reverse=True)
            removed = snapshots[self._config.max_snapshots_per_strategy:]
            self._snapshots[strategy_id] = snapshots[:self._config.max_snapshots_per_strategy]
            logger.info("Retention enforced: removed %d old snapshots for %s", len(removed), strategy_id)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_snapshots": self.total_snapshots,
            "strategy_count": len(self._snapshots),
            "max_per_strategy": self._config.max_snapshots_per_strategy,
            "retention_policy": self._config.retention_policy,
            "initialized": self._initialized,
        }

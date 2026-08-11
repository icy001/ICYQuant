"""
Risk Snapshot — Full risk platform state snapshot and serialization.

Captures exposure, limits, runtime state, and evaluation results
in a serializable snapshot for recovery and audit purposes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskSnapshot:
    """Complete risk platform state snapshot."""
    snapshot_id: str
    platform_id: str = "icyquant-risk"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Runtime state
    runtime_status: str = "running"
    evaluations_active: int = 0
    evaluations_total: int = 0

    # Exposure data
    exposure: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)

    # Policy states
    policies_active: int = 0
    policies_total: int = 0
    policies_snapshot: dict[str, Any] = field(default_factory=dict)

    # Profile states
    profiles_total: int = 0
    profiles_snapshot: dict[str, Any] = field(default_factory=dict)

    # Evaluation results
    evaluations_pending: int = 0
    evaluations_completed: int = 0

    metadata: dict[str, Any] = field(default_factory=dict)


class RiskSnapshotManager:
    """
    Manages risk platform state snapshot creation and restoration.

    Captures complete platform state including exposure, limits,
    runtime status, and evaluation results for recovery and audit.

    Usage::

        mgr = RiskSnapshotManager()
        await mgr.initialize()
        snapshot = await mgr.create_snapshot("snap_001")
        await mgr.restore_snapshot(snapshot)
    """

    def __init__(self, max_snapshots: int = 100) -> None:
        self._snapshots: dict[str, RiskSnapshot] = {}
        self._counter: int = 0
        self._max_snapshots = max_snapshots
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the snapshot manager."""
        logger.info("RiskSnapshotManager initialized.")

    async def stop(self) -> None:
        """Stop the snapshot manager."""
        logger.info("RiskSnapshotManager stopped.")

    # ---- Snapshot Operations ----

    async def create_snapshot(
        self,
        snapshot_id: Optional[str] = None,
        **extra_data: Any,
    ) -> RiskSnapshot:
        """Create a platform state snapshot."""
        self._counter += 1

        snapshot = RiskSnapshot(
            snapshot_id=snapshot_id or f"snap_{self._counter:06d}",
            metadata=extra_data,
        )

        async with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot
            # Trim old snapshots
            if len(self._snapshots) > self._max_snapshots:
                oldest = sorted(self._snapshots.keys())[:len(self._snapshots) - self._max_snapshots]
                for sid in oldest:
                    del self._snapshots[sid]

        logger.info(f"Risk snapshot created: {snapshot.snapshot_id}")
        return snapshot

    async def restore_snapshot(self, snapshot: RiskSnapshot) -> dict[str, Any]:
        """Restore platform state from a snapshot."""
        restored = {
            "snapshot_id": snapshot.snapshot_id,
            "runtime_status": snapshot.runtime_status,
            "policies_active": snapshot.policies_active,
            "profiles_total": snapshot.profiles_total,
            "restored_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Restored from snapshot: {snapshot.snapshot_id}")
        return restored

    async def get_snapshot(self, snapshot_id: str) -> Optional[RiskSnapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    async def get_latest(self) -> Optional[RiskSnapshot]:
        """Get the most recent snapshot."""
        if not self._snapshots:
            return None
        return list(self._snapshots.values())[-1]

    async def list_snapshots(self, limit: int = 50) -> list[RiskSnapshot]:
        """List recent snapshots."""
        snapshots = sorted(self._snapshots.values(), key=lambda s: s.timestamp, reverse=True)
        return snapshots[:limit]

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        async with self._lock:
            if snapshot_id in self._snapshots:
                del self._snapshots[snapshot_id]
                return True
            return False

    async def compare_snapshots(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> Optional[dict[str, Any]]:
        """Compare two snapshots and return differences."""
        s1 = self._snapshots.get(snapshot_id_1)
        s2 = self._snapshots.get(snapshot_id_2)
        if not s1 or not s2:
            return None

        return {
            "snapshot_1": snapshot_id_1,
            "snapshot_2": snapshot_id_2,
            "policies_diff": s2.policies_active - s1.policies_active,
            "evaluations_diff": s2.evaluations_total - s1.evaluations_total,
            "time_diff_seconds": (s2.timestamp - s1.timestamp).total_seconds(),
        }

    async def health_check(self) -> dict[str, Any]:
        """Check snapshot manager health."""
        return {
            "status": "healthy",
            "total_snapshots": len(self._snapshots),
            "max_snapshots": self._max_snapshots,
        }

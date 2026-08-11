"""Execution Snapshot — State snapshot management for EMS recovery.

Provides snapshot creation and restoration for execution state,
enabling recovery after system failures without replaying all events.

Snapshot Strategy::

    Periodic Snapshots → Serialize State → Restore on Recovery → Continue Execution

Usage::

    manager = ExecutionSnapshotManager()
    await manager.create_snapshot(task_id, execution_state)
    state = await manager.restore_snapshot(task_id)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionSnapshot:
    """A point-in-time snapshot of execution state.

    Captures the complete state of an execution at a specific moment,
    enabling state restoration during recovery.

    Attributes:
        snapshot_id: Unique snapshot identifier
        parent_order_id: Parent order identifier
        task_id: Execution task identifier
        created_at: Snapshot creation time
        status: Execution status at snapshot time
        filled_quantity: Cumulative filled quantity
        remaining_quantity: Remaining quantity
        average_price: Volume-weighted average price
        fill_pct: Fill percentage
        current_slice: Current slice index
        total_slices: Total planned slices
        strategy: Algorithm strategy name
        strategy_state: Serialized strategy state
        child_order_ids: Active child order IDs
        metadata: Execution metadata at snapshot time
    """

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_order_id: str = ""
    task_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = ""
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_price: float = 0.0
    fill_pct: float = 0.0
    current_slice: int = 0
    total_slices: int = 0
    strategy: str = ""
    strategy_state: dict[str, Any] = field(default_factory=dict)
    child_order_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "parent_order_id": self.parent_order_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "fill_pct": self.fill_pct,
            "current_slice": self.current_slice,
            "total_slices": self.total_slices,
            "strategy": self.strategy,
            "strategy_state": self.strategy_state,
            "child_order_ids": self.child_order_ids,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionSnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            parent_order_id=data.get("parent_order_id", ""),
            task_id=data.get("task_id", ""),
            status=data.get("status", ""),
            filled_quantity=data.get("filled_quantity", 0.0),
            remaining_quantity=data.get("remaining_quantity", 0.0),
            average_price=data.get("average_price", 0.0),
            fill_pct=data.get("fill_pct", 0.0),
            current_slice=data.get("current_slice", 0),
            total_slices=data.get("total_slices", 0),
            strategy=data.get("strategy", ""),
            strategy_state=data.get("strategy_state", {}),
            child_order_ids=data.get("child_order_ids", []),
            metadata=data.get("metadata", {}),
        )


class ExecutionSnapshotManager:
    """Manages execution state snapshots for recovery.

    Creates periodic snapshots of execution state and enables
    restoration during system recovery. Reduces the need to
    replay all events from the beginning.

    Attributes:
        _snapshots: Map of task_id → list of snapshots
        _max_snapshots_per_task: Maximum snapshots to retain per task
    """

    def __init__(self, max_snapshots_per_task: int = 10) -> None:
        self._snapshots: dict[str, list[ExecutionSnapshot]] = {}
        self._max_snapshots_per_task = max_snapshots_per_task

    # ── Snapshot Management ────────────────────────────────────────

    async def create_snapshot(
        self,
        task_id: str,
        parent_order_id: str,
        status: str,
        filled_quantity: float,
        remaining_quantity: float,
        average_price: float,
        fill_pct: float,
        current_slice: int,
        total_slices: int,
        strategy: str = "",
        strategy_state: Optional[dict[str, Any]] = None,
        child_order_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExecutionSnapshot:
        """Create a new execution state snapshot.

        Args:
            task_id: Execution task identifier
            parent_order_id: Parent order identifier
            status: Current execution status
            filled_quantity: Cumulative filled quantity
            remaining_quantity: Remaining quantity
            average_price: Average fill price
            fill_pct: Fill percentage
            current_slice: Current slice index
            total_slices: Total slices planned
            strategy: Strategy name
            strategy_state: Serialized strategy state
            child_order_ids: Active child order IDs
            metadata: Additional metadata

        Returns:
            Created ExecutionSnapshot
        """
        snapshot = ExecutionSnapshot(
            parent_order_id=parent_order_id,
            task_id=task_id,
            status=status,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_price=average_price,
            fill_pct=fill_pct,
            current_slice=current_slice,
            total_slices=total_slices,
            strategy=strategy,
            strategy_state=strategy_state or {},
            child_order_ids=child_order_ids or [],
            metadata=metadata or {},
        )

        self._snapshots.setdefault(task_id, []).append(snapshot)

        # Prune old snapshots
        snapshots = self._snapshots[task_id]
        while len(snapshots) > self._max_snapshots_per_task:
            removed = snapshots.pop(0)
            logger.debug("Pruned old snapshot: %s", removed.snapshot_id)

        logger.debug(
            "Snapshot created: task=%s slice=%d/%d fill=%.1f%%",
            task_id,
            current_slice,
            total_slices,
            fill_pct * 100,
        )
        return snapshot

    async def get_latest_snapshot(self, task_id: str) -> Optional[ExecutionSnapshot]:
        """Get the most recent snapshot for a task.

        Args:
            task_id: Execution task identifier

        Returns:
            Latest ExecutionSnapshot or None
        """
        snapshots = self._snapshots.get(task_id, [])
        return snapshots[-1] if snapshots else None

    async def get_snapshot_by_id(self, snapshot_id: str) -> Optional[ExecutionSnapshot]:
        """Get a specific snapshot by ID.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            ExecutionSnapshot or None
        """
        for snapshots in self._snapshots.values():
            for snapshot in snapshots:
                if snapshot.snapshot_id == snapshot_id:
                    return snapshot
        return None

    async def get_all_snapshots(self, task_id: str) -> list[ExecutionSnapshot]:
        """Get all snapshots for a task.

        Args:
            task_id: Execution task identifier

        Returns:
            List of snapshots in chronological order
        """
        return list(self._snapshots.get(task_id, []))

    async def restore_from_snapshot(
        self, task_id: str, snapshot_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Restore execution state from a snapshot.

        Returns the state needed to resume execution from the
        snapshot point.

        Args:
            task_id: Execution task identifier
            snapshot_id: Specific snapshot to restore (default: latest)

        Returns:
            State dictionary for restoration, or None
        """
        snapshot = None
        if snapshot_id:
            snapshot = await self.get_snapshot_by_id(snapshot_id)
        else:
            snapshot = await self.get_latest_snapshot(task_id)

        if not snapshot:
            return None

        logger.info(
            "Restoring from snapshot: task=%s snapshot=%s slice=%d",
            task_id,
            snapshot.snapshot_id,
            snapshot.current_slice,
        )
        return snapshot.to_dict()

    # ── Cleanup ────────────────────────────────────────────────────

    async def delete_snapshots(self, task_id: str) -> None:
        """Delete all snapshots for a task.

        Args:
            task_id: Execution task identifier
        """
        self._snapshots.pop(task_id, None)

    async def get_snapshot_count(self, task_id: str) -> int:
        """Get snapshot count for a task.

        Args:
            task_id: Execution task identifier

        Returns:
            Number of snapshots
        """
        return len(self._snapshots.get(task_id, []))

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot manager state."""
        return {
            "tasks": len(self._snapshots),
            "total_snapshots": sum(len(v) for v in self._snapshots.values()),
            "max_per_task": self._max_snapshots_per_task,
        }

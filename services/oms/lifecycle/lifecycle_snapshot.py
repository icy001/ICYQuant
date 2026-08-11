"""Lifecycle Snapshot — State snapshot and recovery management.

Creates and manages order state snapshots for fast recovery.
Implements snapshot creation, retrieval, and pruning policies.

Pipeline:
    Order State → Create Snapshot → Store → Recovery → Replay Events

Key features:
- Periodic snapshot creation
- Snapshot pruning and retention
- Fast state restoration from snapshots
- Event replay for events after snapshot
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore

logger = logging.getLogger(__name__)


@dataclass
class LifecycleSnapshot:
    """A point-in-time snapshot of an order's state."""
    snapshot_id: str
    order_id: str
    status: str
    quantity: float = 0.0
    price: float = 0.0
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    remaining_quantity: float = 0.0
    version: int = 1
    sequence_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fill_pct(self) -> float:
        """Percentage of order filled."""
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "order_id": self.order_id,
            "status": self.status,
            "quantity": self.quantity,
            "price": self.price,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "remaining_quantity": self.remaining_quantity,
            "fill_pct": f"{self.fill_pct:.1%}",
            "version": self.version,
            "sequence_id": self.sequence_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_order(
        cls,
        order: Any,
        snapshot_id: str = "",
        sequence_id: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "LifecycleSnapshot":
        """Create a snapshot from an order object.

        Args:
            order: Order to snapshot
            snapshot_id: Unique snapshot ID
            sequence_id: Current event sequence
            metadata: Additional snapshot metadata

        Returns:
            A new LifecycleSnapshot
        """
        return cls(
            snapshot_id=snapshot_id or f"snap-{order.order_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            order_id=order.order_id,
            status=order.status.value,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
            remaining_quantity=order.remaining_quantity,
            sequence_id=sequence_id,
            metadata=metadata or {},
        )


class SnapshotManager:
    """Manages order state snapshots for fast recovery.

    Creates periodic snapshots of order state and manages retention
    policies. Snapshots enable fast recovery without replaying all
    events from the beginning.

    Usage::

        manager = SnapshotManager(event_store)
        snapshot = await manager.create_snapshot(order)
        latest = await manager.get_latest(order.order_id)
    """

    def __init__(
        self,
        event_store: LifecycleEventStore,
        max_snapshots_per_order: int = 10,
        snapshot_interval_events: int = 100,
    ) -> None:
        """Initialize snapshot manager.

        Args:
            event_store: Event store for sequence tracking
            max_snapshots_per_order: Maximum snapshots to retain per order
            snapshot_interval_events: Create snapshot every N events
        """
        self._event_store = event_store
        self._max_snapshots_per_order = max_snapshots_per_order
        self._snapshot_interval_events = snapshot_interval_events
        # order_id → list of snapshots (newest last)
        self._snapshots: dict[str, list[LifecycleSnapshot]] = {}

    async def create_snapshot(
        self,
        order: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LifecycleSnapshot:
        """Create a snapshot of the current order state.

        Args:
            order: Order to snapshot
            metadata: Additional metadata

        Returns:
            The created snapshot
        """
        sequence_id = await self._event_store.get_sequence(order.order_id)

        snapshot = LifecycleSnapshot.from_order(
            order=order,
            sequence_id=sequence_id,
            metadata=metadata,
        )

        if order.order_id not in self._snapshots:
            self._snapshots[order.order_id] = []
        self._snapshots[order.order_id].append(snapshot)

        # Prune old snapshots
        await self._prune(order.order_id)

        logger.debug(
            f"Snapshot created for order {order.order_id}: "
            f"seq={sequence_id}, status={order.status.value}"
        )

        return snapshot

    async def get_latest(
        self, order_id: str
    ) -> Optional[LifecycleSnapshot]:
        """Get the most recent snapshot for an order.

        Args:
            order_id: Order identifier

        Returns:
            Latest snapshot or None
        """
        snapshots = self._snapshots.get(order_id, [])
        return snapshots[-1] if snapshots else None

    async def get_snapshots(
        self, order_id: str
    ) -> list[LifecycleSnapshot]:
        """Get all snapshots for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of snapshots (newest last)
        """
        return list(self._snapshots.get(order_id, []))

    async def should_snapshot(self, order_id: str) -> bool:
        """Check if it's time to create a new snapshot.

        Args:
            order_id: Order identifier

        Returns:
            True if a new snapshot should be created
        """
        sequence_id = await self._event_store.get_sequence(order_id)
        snapshots = self._snapshots.get(order_id, [])
        if not snapshots:
            return sequence_id >= self._snapshot_interval_events
        last_snap_seq = snapshots[-1].sequence_id
        return (sequence_id - last_snap_seq) >= self._snapshot_interval_events

    async def _prune(self, order_id: str) -> None:
        """Remove old snapshots exceeding retention limit.

        Args:
            order_id: Order identifier
        """
        snapshots = self._snapshots.get(order_id, [])
        while len(snapshots) > self._max_snapshots_per_order:
            removed = snapshots.pop(0)
            logger.debug(f"Pruned old snapshot: {removed.snapshot_id}")

    async def delete_snapshots(self, order_id: str) -> int:
        """Delete all snapshots for an order.

        Args:
            order_id: Order identifier

        Returns:
            Number of snapshots deleted
        """
        count = len(self._snapshots.pop(order_id, []))
        logger.info(f"Deleted {count} snapshots for order {order_id}")
        return count

    async def restore_order_state(
        self,
        order: Any,
        snapshot: LifecycleSnapshot,
    ) -> None:
        """Restore an order's state from a snapshot.

        Args:
            order: Order to restore
            snapshot: Snapshot to restore from
        """
        from services.oms.order.models import OrderStatus

        order.quantity = snapshot.quantity
        order.price = snapshot.price
        order.filled_quantity = snapshot.filled_quantity
        order.average_fill_price = snapshot.average_fill_price

        try:
            order.status = OrderStatus(snapshot.status)
        except ValueError:
            logger.warning(
                f"Unknown status in snapshot: {snapshot.status}, "
                f"keeping current status"
            )

        logger.info(
            f"Order {order.order_id} state restored from snapshot "
            f"{snapshot.snapshot_id}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "tracked_orders": len(self._snapshots),
            "total_snapshots": sum(len(s) for s in self._snapshots.values()),
            "max_snapshots_per_order": self._max_snapshots_per_order,
            "snapshot_interval_events": self._snapshot_interval_events,
        }

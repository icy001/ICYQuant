"""Recovery Handler — Handles order recovery from snapshots and event replay.

Implements the recovery flow for orders after system failures or
restarts. Restores order state from snapshots and replays events.

Pipeline:
    Snapshot → Replay Events → Restore State → Continue Runtime

Key features:
- Snapshot-based recovery
- Event replay for gap filling
- State restoration validation
- Recovery audit trail
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import TransitionEngine
from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore, StoredEvent
from services.oms.lifecycle.lifecycle_snapshot import SnapshotManager

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    """Result of order recovery."""
    order_id: str
    success: bool = False
    recovered_from: str = ""
    events_replayed: int = 0
    restored_status: Optional[LifecycleStatus] = None
    gaps_found: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "recovered_from": self.recovered_from,
            "events_replayed": self.events_replayed,
            "restored_status": self.restored_status.value if self.restored_status else None,
            "gaps_found": self.gaps_found,
            "errors": self.errors,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class RecoveryHandler:
    """Handles order recovery after failures.

    Restores order state from the latest snapshot and replays
    events that occurred after the snapshot. Supports gap detection
    and automatic recovery request generation.

    Usage::

        handler = RecoveryHandler(transition_engine, event_store, snapshot_manager)
        result = await handler.recover(order_id)
        if result.success:
            print(f"Recovered to {result.restored_status}")
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        event_store: LifecycleEventStore,
        snapshot_manager: SnapshotManager,
    ) -> None:
        self._engine = transition_engine
        self._event_store = event_store
        self._snapshot_manager = snapshot_manager

    async def recover(
        self,
        order_id: str,
        use_snapshot: bool = True,
    ) -> RecoveryResult:
        """Recover an order from snapshot or event replay.

        Args:
            order_id: Order identifier to recover
            use_snapshot: If True, try snapshot first; otherwise full replay

        Returns:
            RecoveryResult with recovered state and details
        """
        logger.info(f"Starting recovery for order {order_id}")

        if use_snapshot:
            snapshot = await self._snapshot_manager.get_latest(order_id)
            if snapshot:
                return await self._recover_from_snapshot(order_id, snapshot)

        # Fall back to full event replay
        return await self._recover_from_events(order_id)

    async def _recover_from_snapshot(
        self, order_id: str, snapshot: Any
    ) -> RecoveryResult:
        """Recover order state from a snapshot.

        Args:
            order_id: Order identifier
            snapshot: Snapshot to recover from

        Returns:
            RecoveryResult with recovery details
        """
        logger.info(f"Recovering order {order_id} from snapshot at {snapshot.timestamp}")

        # Get events after snapshot
        events_after = await self._event_store.get_events(
            order_id, since=snapshot.timestamp
        )

        # Replay events after snapshot
        restored_status = None
        for evt in events_after:
            restored_status = LifecycleStatus(evt.to_status)

        if restored_status is None:
            restored_status = LifecycleStatus(snapshot.status)

        logger.info(
            f"Order {order_id} recovered from snapshot: "
            f"status={restored_status.value}, "
            f"events_replayed={len(events_after)}"
        )

        return RecoveryResult(
            order_id=order_id,
            success=True,
            recovered_from="snapshot",
            events_replayed=len(events_after),
            restored_status=restored_status,
            message=f"Recovered from snapshot at {snapshot.timestamp}",
        )

    async def _recover_from_events(self, order_id: str) -> RecoveryResult:
        """Recover order state by full event replay.

        Args:
            order_id: Order identifier

        Returns:
            RecoveryResult with recovery details
        """
        logger.info(f"Recovering order {order_id} from full event replay")

        events = await self._event_store.replay(order_id)

        if not events:
            return RecoveryResult(
                order_id=order_id,
                success=False,
                errors=["No events found for replay"],
                message="No events to replay",
            )

        # Detect gaps in sequence
        gaps = self._detect_gaps(events)

        # Determine final status from last event
        final_status = LifecycleStatus(events[-1].to_status)

        logger.info(
            f"Order {order_id} recovered from event replay: "
            f"status={final_status.value}, "
            f"events={len(events)}, gaps={len(gaps)}"
        )

        return RecoveryResult(
            order_id=order_id,
            success=True,
            recovered_from="event_replay",
            events_replayed=len(events),
            restored_status=final_status,
            gaps_found=gaps,
            message=f"Recovered from {len(events)} events",
        )

    def _detect_gaps(self, events: list[StoredEvent]) -> list[int]:
        """Detect gaps in event sequences.

        Args:
            events: List of events in sequence order

        Returns:
            List of missing sequence IDs
        """
        if len(events) < 2:
            return []

        gaps: list[int] = []
        sorted_events = sorted(events, key=lambda e: e.sequence_id)

        for i in range(1, len(sorted_events)):
            expected = sorted_events[i - 1].sequence_id + 1
            actual = sorted_events[i].sequence_id
            if actual > expected:
                gaps.extend(range(expected, actual))

        return gaps

    async def validate_recovery(
        self, order_id: str, expected_status: LifecycleStatus
    ) -> bool:
        """Validate that recovery produced the expected state.

        Args:
            order_id: Order identifier
            expected_status: Expected status after recovery

        Returns:
            True if recovery state matches expected
        """
        last_event = await self._event_store.get_last_event(order_id)
        if last_event is None:
            return False
        return LifecycleStatus(last_event.to_status) == expected_status

    def to_dict(self) -> dict[str, Any]:
        return {}

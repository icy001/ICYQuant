"""OrderRecovery — high-level order state recovery.

Handles recovery scenarios:
    A. Projection corrupted → Replay from event store.
    B. Snapshot corrupted → Replay from event store (ignore snapshot).
    C. Event hash corrupted → Cannot auto-recover; raise alert.

The recovery process is:
    Projection
        ↓
    Integrity Check
        ↓
    Snapshot Check
        ↓
    Event Stream Check
        ↓
    Replay
        ↓
    Rebuild
        ↓
    Recreate Projection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from services.oms.events.order_event_errors import (
    EventHashChainError,
    EventSequenceGapError,
)
from services.oms.event_store.order_event_store import OrderEventStore
from services.oms.event_store.event_store_snapshot import SnapshotStore
from services.oms.event_store.event_store_errors import (
    EventStreamNotFoundError,
    SnapshotValidationError,
)
from services.oms.projection.order_projection import OrderProjection
from services.oms.projection.order_projector import OrderProjector
from .order_rebuilder import OrderRebuilder


class RecoveryStatus(Enum):
    """Status of a recovery attempt."""

    RECOVERED = auto()
    RECOVERED_FROM_SNAPSHOT = auto()
    RECOVERED_FROM_SCRATCH = auto()
    SNAPSHOT_DISCARDED = auto()
    INTEGRITY_FAILURE = auto()
    STREAM_NOT_FOUND = auto()
    UNKNOWN_FAILURE = auto()

    @property
    def is_success(self) -> bool:
        return self in (
            RecoveryStatus.RECOVERED,
            RecoveryStatus.RECOVERED_FROM_SNAPSHOT,
            RecoveryStatus.RECOVERED_FROM_SCRATCH,
            RecoveryStatus.SNAPSHOT_DISCARDED,
        )

    @property
    def label(self) -> str:
        _labels = {
            RecoveryStatus.RECOVERED: "Recovered",
            RecoveryStatus.RECOVERED_FROM_SNAPSHOT: "Recovered from snapshot",
            RecoveryStatus.RECOVERED_FROM_SCRATCH: "Recovered from scratch",
            RecoveryStatus.SNAPSHOT_DISCARDED: "Snapshot discarded, full replay",
            RecoveryStatus.INTEGRITY_FAILURE: "Event integrity failure",
            RecoveryStatus.STREAM_NOT_FOUND: "Stream not found",
            RecoveryStatus.UNKNOWN_FAILURE: "Unknown failure",
        }
        return _labels[self]


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    order_id: str = ""
    status: RecoveryStatus = RecoveryStatus.UNKNOWN_FAILURE
    projection: Optional[OrderProjection] = None
    event_count: int = 0
    snapshot_used: bool = False
    snapshot_discarded: bool = False
    error_message: str = ""
    recovery_time: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.status.is_success


class OrderRecovery:
    """High-level order recovery coordinator.

    Orchestrates the recovery process, trying multiple strategies:
    1. Snapshot + delta replay
    2. Full replay from event store
    3. Report integrity failure if event store is corrupted
    """

    def __init__(self, store: OrderEventStore,
                 projector: Optional[OrderProjector] = None,
                 snapshot_store: Optional[SnapshotStore] = None) -> None:
        self._store = store
        self._snapshots = snapshot_store or SnapshotStore()
        self._projector = projector or OrderProjector(
            store, self._snapshots, use_snapshots=True,
        )
        self._rebuilder = OrderRebuilder(store, self._snapshots)

    def recover(self, order_id: str) -> RecoveryResult:
        """Recover an order's state.

        Tries snapshot first, then full replay. If the event store
        itself is corrupted (hash chain break), returns
        INTEGRITY_FAILURE.
        """
        import time
        start = time.time()

        result = RecoveryResult(order_id=order_id)

        # Check if stream exists
        if not self._store.stream_exists(order_id):
            result.status = RecoveryStatus.STREAM_NOT_FOUND
            result.error_message = f"No event stream for {order_id}"
            result.recovery_time = time.time() - start
            return result

        result.event_count = self._store.count(order_id)

        # Try recovery with snapshot
        try:
            snapshot = self._snapshots.get(order_id)
            if snapshot is not None and snapshot.verify():
                # Validate snapshot against event store
                stream = self._store.get_stream(order_id)
                snap_event = stream.get_event(snapshot.sequence)
                if snap_event and snapshot.verify_against_event(
                    snap_event.event_hash,
                ):
                    # Valid snapshot — replay delta
                    projection = self._rebuilder.rebuild(order_id)
                    result.projection = projection
                    result.status = RecoveryStatus.RECOVERED_FROM_SNAPSHOT
                    result.snapshot_used = True
                    result.recovery_time = time.time() - start
                    # Update projector cache
                    self._projector.apply_events(
                        self._store.read(order_id),
                    ) if False else None
                    self._projector._projections[order_id] = projection
                    return result
                else:
                    # Snapshot doesn't match — discard
                    self._snapshots.delete(order_id)
                    result.snapshot_discarded = True
            elif snapshot is not None and not snapshot.verify():
                # Snapshot hash invalid — discard
                self._snapshots.delete(order_id)
                result.snapshot_discarded = True

            # Full replay
            projection = self._rebuilder.rebuild_from_scratch(order_id)
            result.projection = projection
            if result.snapshot_discarded:
                result.status = RecoveryStatus.SNAPSHOT_DISCARDED
            else:
                result.status = RecoveryStatus.RECOVERED_FROM_SCRATCH
            result.recovery_time = time.time() - start
            # Update projector cache
            self._projector._projections[order_id] = projection
            return result

        except EventHashChainError as e:
            result.status = RecoveryStatus.INTEGRITY_FAILURE
            result.error_message = (
                f"Event hash chain broken: {e.message}"
            )
            result.recovery_time = time.time() - start
            return result

        except EventSequenceGapError as e:
            result.status = RecoveryStatus.INTEGRITY_FAILURE
            result.error_message = (
                f"Event sequence gap: expected {e.expected}, got {e.actual}"
            )
            result.recovery_time = time.time() - start
            return result

        except Exception as e:
            result.status = RecoveryStatus.UNKNOWN_FAILURE
            result.error_message = str(e)
            result.recovery_time = time.time() - start
            return result

    def recover_all(self) -> list:
        """Recover all orders in the event store."""
        results = []
        for order_id in self._store.get_all_order_ids():
            results.append(self.recover(order_id))
        return results

    def check_integrity(self, order_id: str) -> bool:
        """Check the integrity of an order's event stream."""
        return self._rebuilder.validate_integrity(order_id)

    def check_all_integrity(self) -> dict:
        """Check integrity of all order event streams.

        Returns a dict of order_id → bool (True = valid).
        """
        return {
            oid: self.check_integrity(oid)
            for oid in self._store.get_all_order_ids()
        }

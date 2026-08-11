"""EventStoreSnapshot — performance optimization for event replay.

Snapshots cache the order state at a specific sequence number,
avoiding the need to replay from event 1 every time.

IMPORTANT: Snapshot is NOT the source of truth. It is a performance
optimization. The Event Store remains the sole source of truth.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.oms.domain.order_status import OrderStatus


@dataclass
class EventStoreSnapshot:
    """A snapshot of order state at a specific sequence.

    Fields:
        order_id: The order this snapshot belongs to.
        sequence: The event sequence this snapshot was taken at.
        status: Order status at this sequence.
        filled_quantity: Cumulative filled quantity.
        remaining_quantity: Remaining quantity.
        cancelled_quantity: Cancelled quantity.
        average_price: VWAP at this point.
        last_event_hash: Hash of the event at this sequence.
        snapshot_hash: Hash of the snapshot content (for validation).
        created_at: When this snapshot was created.
    """

    order_id: str = ""
    sequence: int = 0
    status: OrderStatus = OrderStatus.RECEIVED

    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    cancelled_quantity: float = 0.0
    original_quantity: float = 0.0
    average_price: float = 0.0

    last_event_hash: str = ""
    snapshot_hash: str = ""
    created_at: float = field(default_factory=lambda: __import__("time").time())

    extra: Dict[str, Any] = field(default_factory=dict)

    # ══════════════════════════════════════════════════
    #  Factory
    # ══════════════════════════════════════════════════

    @classmethod
    def create(cls, order_id: str, sequence: int,
               status: OrderStatus,
               filled_quantity: float = 0,
               remaining_quantity: float = 0,
               cancelled_quantity: float = 0,
               original_quantity: float = 0,
               average_price: float = 0,
               last_event_hash: str = "",
               **extra: Any) -> "EventStoreSnapshot":
        snap = cls(
            order_id=order_id,
            sequence=sequence,
            status=status,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            cancelled_quantity=cancelled_quantity,
            original_quantity=original_quantity,
            average_price=average_price,
            last_event_hash=last_event_hash,
            extra=dict(extra),
        )
        snap.snapshot_hash = snap._compute_hash()
        return snap

    # ══════════════════════════════════════════════════
    #  Validation
    # ══════════════════════════════════════════════════

    def _compute_hash(self) -> str:
        content = (
            f"{self.order_id}:{self.sequence}:{self.status.name}:"
            f"{self.filled_quantity}:{self.remaining_quantity}:"
            f"{self.cancelled_quantity}:{self.original_quantity}:"
            f"{self.average_price}:{self.last_event_hash}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        """Verify that the snapshot hash is valid."""
        return self.snapshot_hash == self._compute_hash()

    def verify_against_event(self, event_hash: str) -> bool:
        """Verify that the snapshot matches the expected event hash."""
        return self.last_event_hash == event_hash

    # ══════════════════════════════════════════════════
    #  Serialization
    # ══════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "sequence": self.sequence,
            "status": self.status.name,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "cancelled_quantity": self.cancelled_quantity,
            "original_quantity": self.original_quantity,
            "average_price": self.average_price,
            "last_event_hash": self.last_event_hash,
            "snapshot_hash": self.snapshot_hash,
            "created_at": self.created_at,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventStoreSnapshot":
        return cls(
            order_id=d["order_id"],
            sequence=d["sequence"],
            status=OrderStatus[d["status"]],
            filled_quantity=d.get("filled_quantity", 0),
            remaining_quantity=d.get("remaining_quantity", 0),
            cancelled_quantity=d.get("cancelled_quantity", 0),
            original_quantity=d.get("original_quantity", 0),
            average_price=d.get("average_price", 0),
            last_event_hash=d.get("last_event_hash", ""),
            snapshot_hash=d.get("snapshot_hash", ""),
            created_at=d.get("created_at", time.time()),
            extra=dict(d.get("extra", {})),
        )


class SnapshotStore:
    """In-memory snapshot store (for testing/development)."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, EventStoreSnapshot] = {}

    def save(self, snapshot: EventStoreSnapshot) -> None:
        self._snapshots[snapshot.order_id] = snapshot

    def get(self, order_id: str) -> Optional[EventStoreSnapshot]:
        return self._snapshots.get(order_id)

    def delete(self, order_id: str) -> None:
        self._snapshots.pop(order_id, None)

    def exists(self, order_id: str) -> bool:
        return order_id in self._snapshots

"""OrderEvent — the core event entity for order event sourcing."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_event_type import OrderEventType
from .order_event_metadata import OrderEventMetadata


def _compute_hash(event_id: str, order_id: str,
                  event_type: OrderEventType,
                  sequence: int, timestamp: float,
                  payload: Dict[str, Any],
                  previous_event_hash: str) -> str:
    """Compute SHA-256 hash of event content."""
    content = json.dumps({
        "event_id": event_id,
        "order_id": order_id,
        "event_type": event_type.name,
        "sequence": sequence,
        "timestamp": timestamp,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
    }, sort_keys=True, default=str)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class OrderEvent:
    """A single event in an order's event stream.

    Events are immutable once appended. The hash chain
    (previous_event_hash → event_hash) ensures tamper detection.

    Every event carries lineage information (lineage_id, flow_id,
    certificate_id) to maintain the Control Lineage from Commit 21.
    """

    # ── Identity ───────────────────────────────────
    event_id: str = field(
        default_factory=lambda: f"EVT-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    order_id: str = ""

    # ── Event ──────────────────────────────────────
    event_type: OrderEventType = OrderEventType.ORDER_CREATED
    sequence: int = 0
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    # ── Lineage ────────────────────────────────────
    lineage_id: str = ""
    flow_id: str = ""
    certificate_id: str = ""

    # ── Content ────────────────────────────────────
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: OrderEventMetadata = field(default_factory=OrderEventMetadata)

    # ── Hash chain ─────────────────────────────────
    previous_event_hash: str = ""
    event_hash: str = ""

    # ══════════════════════════════════════════════════
    #  Factory
    # ══════════════════════════════════════════════════

    @classmethod
    def create(cls, order_id: str,
               event_type: OrderEventType,
               sequence: int,
               lineage_id: str = "",
               flow_id: str = "",
               certificate_id: str = "",
               payload: Optional[Dict[str, Any]] = None,
               metadata: Optional[OrderEventMetadata] = None,
               previous_event_hash: str = "") -> "OrderEvent":
        """Create a new event (unsealed — call seal() to compute hash)."""
        return cls(
            order_id=order_id,
            event_type=event_type,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload=dict(payload or {}),
            metadata=metadata or OrderEventMetadata(),
            previous_event_hash=previous_event_hash,
        )

    # ══════════════════════════════════════════════════
    #  Hashing
    # ══════════════════════════════════════════════════

    def compute_hash(self) -> str:
        """Compute the event hash based on content."""
        return _compute_hash(
            self.event_id, self.order_id, self.event_type,
            self.sequence, self.timestamp, self.payload,
            self.previous_event_hash,
        )

    def seal(self) -> "OrderEvent":
        """Compute and set the event hash. Idempotent."""
        if not self.event_hash:
            self.event_hash = self.compute_hash()
        return self

    @property
    def is_sealed(self) -> bool:
        return bool(self.event_hash)

    def verify_hash(self) -> bool:
        """Verify that the stored hash matches the computed hash."""
        if not self.event_hash:
            return False
        return self.event_hash == self.compute_hash()

    # ══════════════════════════════════════════════════
    #  Properties
    # ══════════════════════════════════════════════════

    @property
    def is_terminal(self) -> bool:
        return self.event_type.is_terminal

    @property
    def has_lineage(self) -> bool:
        return bool(self.lineage_id)

    # ══════════════════════════════════════════════════
    #  Serialization
    # ══════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "event_type": self.event_type.name,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "lineage_id": self.lineage_id,
            "flow_id": self.flow_id,
            "certificate_id": self.certificate_id,
            "payload": dict(self.payload),
            "metadata": self.metadata.to_dict(),
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderEvent":
        return cls(
            event_id=d["event_id"],
            order_id=d["order_id"],
            event_type=OrderEventType[d["event_type"]],
            sequence=d["sequence"],
            timestamp=d["timestamp"],
            lineage_id=d.get("lineage_id", ""),
            flow_id=d.get("flow_id", ""),
            certificate_id=d.get("certificate_id", ""),
            payload=dict(d.get("payload", {})),
            metadata=OrderEventMetadata.from_dict(d.get("metadata", {})),
            previous_event_hash=d.get("previous_event_hash", ""),
            event_hash=d.get("event_hash", ""),
        )

    def fingerprint(self) -> str:
        """A short fingerprint for deduplication comparison."""
        return _compute_hash(
            self.event_id, self.order_id, self.event_type,
            self.sequence, 0, self.payload, "",
        )

    def __repr__(self) -> str:
        return (
            f"OrderEvent({self.event_id}, {self.event_type.name}, "
            f"seq={self.sequence}, order={self.order_id})"
        )

"""
Cross-domain Event Envelope.

All domain events transported across the Event Bus are wrapped in
a unified EventEnvelope carrying metadata for tracing, ordering,
and idempotency.

The envelope is the contract that every producer and consumer
must respect — no raw domain events are ever placed on the bus.

Architecture:

    Producer Domain
         |
         v
    EventEnvelope  ──>  Event Bus
                           |
          ┌────────────────┼────────────────┐
          v                v                v
    Position            Ledger             Risk
    Consumer           Consumer          Consumer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional
from uuid import uuid4


# ── Event Delivery State ──────────────────────────────────────────────

class DeliveryState(str, Enum):
    """Lifecycle of a single event delivery attempt."""

    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


# ── Consistency State ─────────────────────────────────────────────────

class ConsistencyState(str, Enum):
    """Cross-domain eventual-consistency tracking."""

    SYNCED = "SYNCED"
    LAGGING = "LAGGING"
    RECOVERING = "RECOVERING"
    MISMATCHED = "MISMATCHED"


# ── Event Envelope ────────────────────────────────────────────────────

@dataclass(frozen=True)
class EventEnvelope:
    """
    Unified wrapper for every event published on the Event Bus.

    Fields
    ------
    event_id : str
        Globally unique identifier for this event instance.
        Primary idempotency key across all domains.

    event_type : str
        Domain event type discriminator (e.g. "ORDER_FILLED").

    event_version : int
        Schema version of this event type.
        Allows v1 and v2 consumers to coexist during migration.

    aggregate_type : str
        The aggregate root this event belongs to (e.g. "ORDER").

    aggregate_id : str
        Identity of the specific aggregate instance.

    aggregate_version : int
        Monotonically-increasing sequence number within the
        aggregate stream.  Used for ordering detection.

    occurred_at : datetime
        UTC timestamp when the event was produced.

    producer : str
        Domain / service that published the event (e.g. "OMS").

    correlation_id : str
        Links all events triggered by the same external action
        (strategy signal through to ledger entry).

    causation_id : Optional[str]
        Points to the event_id that directly caused this event,
        forming a complete causal chain.

    lineage_id : str
        Linage identifier shared by all events in a trading
        lineage — from order to position to ledger to risk.

    payload : Mapping[str, Any]
        The domain-specific event body.

    metadata : Mapping[str, Any]
        Extensible metadata (e.g. tracing span id, tenant).
    """

    event_id: str = field(default_factory=lambda: f"EVT-{uuid4().hex[:12].upper()}")
    event_type: str = ""
    event_version: int = 1

    aggregate_type: str = ""
    aggregate_id: str = ""
    aggregate_version: int = 1

    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    producer: str = ""

    correlation_id: str = ""
    causation_id: Optional[str] = None

    lineage_id: str = ""

    payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # ── helpers ─────────────────────────────────────────────────

    @classmethod
    def from_event(
        cls,
        event_id: str,
        event_type: str,
        event_version: int,
        aggregate_type: str,
        aggregate_id: str,
        aggregate_version: int,
        producer: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: str = "",
        causation_id: Optional[str] = None,
        lineage_id: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "EventEnvelope":
        """Construct an envelope from raw event data."""
        return cls(
            event_id=event_id,
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            producer=producer,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            payload=payload,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "occurred_at": self.occurred_at.isoformat(),
            "producer": self.producer,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EventEnvelope":
        """Deserialize from a dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            event_version=data.get("event_version", 1),
            aggregate_type=data.get("aggregate_type", ""),
            aggregate_id=data.get("aggregate_id", ""),
            aggregate_version=data.get("aggregate_version", 1),
            occurred_at=_parse_datetime(data["occurred_at"]),
            producer=data.get("producer", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id"),
            lineage_id=data.get("lineage_id", ""),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )

    # ── delivery tracking (mutable per-consumer) ────────────────────

    def with_delivery_state(
        self, state: DeliveryState, consumer_group: str
    ) -> "DeliveryRecord":
        """Create a per-consumer delivery record."""
        return DeliveryRecord(
            envelope=self,
            consumer_group=consumer_group,
            state=state,
        )


@dataclass(frozen=True)
class DeliveryRecord:
    """Tracks delivery of a single event to a single consumer group."""

    envelope: EventEnvelope
    consumer_group: str
    state: DeliveryState = DeliveryState.PENDING
    attempt: int = 0
    last_error: Optional[str] = None
    delivered_at: Optional[datetime] = None


# ── helpers ────────────────────────────────────────────────────────────


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))

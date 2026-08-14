"""Order Request domain event model.

Events are append-only records of *facts*: they describe why an aggregate
changed, never how the entire system looks.  A state records *what is now*;
an event records *what happened* (see
:class:`~services.order.request.event_types.OrderRequestEventType`).

The event carries enough correlation metadata so the whole trading chain
(Signal -> Intent -> Risk Decision -> Authorization -> Order Request ->
Event) can be linked through ``correlation_id``, and so a single order
request's life can be rebuilt through ``aggregate_id`` + ``sequence``.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Optional

from services.order.request.event_types import OrderRequestEventType
from services.order.request.state import OrderRequestState


@dataclass(frozen=True)
class OrderRequestEvent:
    """An immutable, append-only domain event for an order request.

    Attributes:
        event_id: Globally unique event identifier (never the aggregate id —
            one aggregate produces many events).
        event_type: What happened (explicit, never a generic "updated").
        aggregate_id: The order request id this event belongs to.
        aggregate_type: Stable aggregate type, always ``"OrderRequest"``.
        correlation_id: Links the whole trading chain together.
        causation_id: The event id of the event that caused this one; ``None``
            for the first event of an aggregate.
        sequence: Aggregate-local, strictly monotonic sequence number.
        timestamp: Event creation time (unix epoch seconds).
        state: Aggregate state *after* this event was applied.
        payload: Minimal business facts.  An event describes facts, it never
            copies the whole database.
    """

    event_id: str
    event_type: OrderRequestEventType
    aggregate_id: str
    aggregate_type: str
    correlation_id: str
    causation_id: Optional[str]
    sequence: int
    timestamp: float
    state: OrderRequestState
    payload: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Return a serializable representation for the event bus / storage."""
        return {
            "event_id": self.event_id,
            "event_type": str(self.event_type.value),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "state": str(self.state.value),
            "payload": dict(self.payload),
        }


class OutboxStatus(str, Enum):
    """Delivery status of an outbox record."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OutboxRecord:
    """A transactional outbox record.

    The state transition and the outbox record are persisted atomically; the
    event bus only propagates asynchronously afterwards.  If the bus is down
    the record stays ``PENDING`` and is retried later — the event is never
    lost (At-Least-Once delivery, downstream consumers de-duplicate by
    ``event_id``).
    """

    event_id: str
    aggregate_id: str
    event_type: OrderRequestEventType
    sequence: int
    payload: Dict[str, Any]
    created_at: float
    published_at: Optional[float] = None
    status: OutboxStatus = OutboxStatus.PENDING

    @classmethod
    def from_event(cls, event: OrderRequestEvent) -> "OutboxRecord":
        """Build a PENDING outbox record from a domain event."""
        return cls(
            event_id=event.event_id,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            sequence=event.sequence,
            payload=dict(event.payload),
            created_at=event.timestamp,
        )

    def mark_published(self, published_at: Optional[float] = None) -> "OutboxRecord":
        """Return a copy of this record with ``PUBLISHED`` status."""
        return replace(self, status=OutboxStatus.PUBLISHED, published_at=published_at)

    def mark_failed(self) -> "OutboxRecord":
        """Return a copy of this record with ``FAILED`` status."""
        return replace(self, status=OutboxStatus.FAILED)


__all__ = [
    "OrderRequestEvent",
    "OutboxRecord",
    "OutboxStatus",
]

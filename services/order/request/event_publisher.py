"""Order request event publisher, event bus boundary and outbox.

The publisher is deliberately decoupled from any concrete broker (Kafka,
RabbitMQ, Redis Streams, NATS): it speaks to an :class:`EventBus` abstraction.
The publisher does **not** re-order, repair or infer events — ordering is the
responsibility of the ``OrderRequest`` aggregate and its ``sequence``; the
publisher only publishes.

Reliability boundary (transactional outbox):

- The aggregate state and the outbox record are persisted atomically.
- The event bus only propagates asynchronously afterwards.
- If the bus is down the outbox record stays ``PENDING`` and is retried
  later — the event is never lost (At-Least-Once).
- Consumers de-duplicate by ``event_id`` (idempotency).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Tuple

from services.order.request.events import (
    OrderRequestEvent,
    OutboxRecord,
    OutboxStatus,
)


class EventBusUnavailable(RuntimeError):
    """Raised when the event bus cannot accept a publish (e.g. it is down)."""


class EventBus(Protocol):
    """Event bus abstraction (Kafka / RabbitMQ / Redis Streams / NATS ...)."""

    def publish(self, event: OrderRequestEvent) -> None:
        """Deliver ``event`` to the bus.

        Raises:
            EventBusUnavailable: if the bus cannot accept the event.
        """


class InMemoryEventBus:
    """In-memory event bus for tests and single-process deployments."""

    def __init__(self) -> None:
        self.events: List[OrderRequestEvent] = []
        self.handlers: List[object] = []

    def subscribe(self, handler) -> None:
        self.handlers.append(handler)

    def publish(self, event: OrderRequestEvent) -> None:
        self.events.append(event)
        for handler in self.handlers:
            handler(event)


class OrderRequestOutbox:
    """Transactional outbox store (PENDING -> PUBLISHED / FAILED).

    Records are append-only: a record is created with ``PENDING`` status when
    the state change is committed.  A relay publishes ``PENDING`` records and
    marks them ``PUBLISHED`` (or ``FAILED`` when retries are exhausted).
    """

    def __init__(self) -> None:
        self._records: Dict[str, OutboxRecord] = {}

    def append(self, event: OrderRequestEvent) -> OutboxRecord:
        """Store ``event`` as a PENDING outbox record (idempotent by event id)."""
        existing = self._records.get(event.event_id)
        if existing is not None:
            return existing
        record = OutboxRecord.from_event(event)
        self._records[event.event_id] = record
        return record

    def mark_published(
        self, event_id: str, *, published_at: Optional[float] = None
    ) -> OutboxRecord:
        record = self._require(event_id)
        updated = record.mark_published(published_at=published_at)
        self._records[event_id] = updated
        return updated

    def mark_failed(self, event_id: str) -> OutboxRecord:
        record = self._require(event_id)
        updated = record.mark_failed()
        self._records[event_id] = updated
        return updated

    def get(self, event_id: str) -> Optional[OutboxRecord]:
        return self._records.get(event_id)

    def get_pending(self) -> List[OutboxRecord]:
        return [
            record
            for record in self._records.values()
            if record.status == OutboxStatus.PENDING
        ]

    def get_failed(self) -> List[OutboxRecord]:
        return [
            record
            for record in self._records.values()
            if record.status == OutboxStatus.FAILED
        ]

    def all(self) -> Tuple[OutboxRecord, ...]:
        return tuple(self._records.values())

    def _require(self, event_id: str) -> OutboxRecord:
        record = self._records.get(event_id)
        if record is None:
            raise KeyError(f"no outbox record for event id: {event_id}")
        return record


class OrderRequestEventPublisher:
    """Publishes order request events to the event bus.

    Idempotency: publishing the same event (same ``event_id``) twice is a
    no-op, so a network retry never delivers a duplicate to the bus.

    The publisher does **not** re-order events; ``sequence`` correctness is
    guaranteed by the aggregate.
    """

    def __init__(self, *, bus: Optional[EventBus] = None) -> None:
        self.bus: EventBus = bus if bus is not None else InMemoryEventBus()
        #: Set to ``True`` to simulate an unavailable event bus.
        self.fail: bool = False
        self._published: Dict[str, int] = {}

    def publish(self, event: OrderRequestEvent) -> None:
        """Publish ``event`` once (duplicates are ignored)."""
        if event.event_id in self._published:
            return
        if self.fail:
            raise EventBusUnavailable("event bus unavailable")
        self.bus.publish(event)
        self._published[event.event_id] = 1

    def published_count(self, event_id: str) -> int:
        """Number of times ``event_id`` was published (0 or 1)."""
        return self._published.get(event_id, 0)

    def published_event_ids(self) -> Tuple[str, ...]:
        return tuple(self._published.keys())


__all__ = [
    "EventBus",
    "EventBusUnavailable",
    "InMemoryEventBus",
    "OrderRequestEventPublisher",
    "OrderRequestOutbox",
]
